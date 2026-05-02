"""
KiCad PCB to CadQuery

Generates 3D CAD models of keyboard case plates based on KiCad PCB design files. The script reads
the PCB file, extracts graphic items from specified layers, converts them to CadQuery edges, and
builds 3D models of the top and bottom plates with cutouts for components and mounting holes.

Documentation:

- kiutils: https://kiutils.readthedocs.io/en/latest/
- CadQuery: https://cadquery.readthedocs.io/en/latest/

Prior art:

- https://github.com/meadiode/EMES/blob/main/3dcad/housing/housing.py
"""

import argparse
import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path

import cadquery as cq
from cadquery.occ_impl.shapes import edgesToWires
from kiutils.board import Board

cwd = Path(__file__).parent

parser = argparse.ArgumentParser(
    prog="generate-case", description="Display generated keyboard case plates"
)
parser.add_argument("-p", "--preview", action="store_true")
args = parser.parse_args()

if args.preview:
    from ocp_vscode import set_defaults, show

    set_defaults(pan_speed=1, zoom_speed=1, timeit=1)

# Transform geometry from PCB file to CadQuery edges -----------------------------------------------

def item_to_edges(item):
    """Convert a KiCad PCB graphic item to CadQuery edges (Y-axis flipped to match CQ convention)."""
    t = item.__class__.__name__
    if t in ("GrLine", "FpLine"):
        return [
            cq.Edge.makeLine(
                cq.Vector(item.start.X, -item.start.Y, 0),
                cq.Vector(item.end.X, -item.end.Y, 0),
            )
        ]
    elif t in ("GrCurve", "FpCurve"):
        return [
            cq.Edge.makeBezier([cq.Vector(pt.X, -pt.Y, 0) for pt in item.coordinates])
        ]
    elif t in ("GrPoly", "FpPoly"):
        pts = [cq.Vector(pt.X, -pt.Y, 0) for pt in item.coordinates]
        return [
            cq.Edge.makeLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))
        ]
    elif t in ("GrArc", "FpArc"):
        return [
            cq.Edge.makeThreePointArc(
                cq.Vector(item.start.X, -item.start.Y, 0),
                cq.Vector(item.mid.X, -item.mid.Y, 0),
                cq.Vector(item.end.X, -item.end.Y, 0),
            )
        ]
    elif t in ("GrRect", "FpRect"):
        s, e = item.start, item.end
        corners = [
            cq.Vector(s.X, -s.Y, 0),
            cq.Vector(e.X, -s.Y, 0),
            cq.Vector(e.X, -e.Y, 0),
            cq.Vector(s.X, -e.Y, 0),
        ]
        return [cq.Edge.makeLine(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    elif t in ("GrCircle", "FpCircle"):
        dx = item.end.X - item.center.X
        dy = item.end.Y - item.center.Y
        return [
            cq.Edge.makeCircle(
                sqrt(dx * dx + dy * dy), cq.Vector(item.center.X, -item.center.Y, 0)
            )
        ]
    return []

def normalize_wires(wires):
    # Flipping KiCad's Y axis reflects loop winding, so normalize planar wires before sketching.
    normalized = []
    for wire in wires:
        try:
            if cq.Face.makeFromWires(wire).normalAt().z < 0:
                wire = cq.Shape.cast(wire.wrapped.Reversed())
        except ValueError:
            pass
        normalized.append(wire)
    return normalized


layer_wires = defaultdict(list)
board = Board().from_file(cwd / "cweep.kicad_pcb")

# Transform board graphics and footprint graphics into board space, but assemble each transformed
# source separately so edgesToWires does not merge unrelated footprint geometry on the same layer.
for graphic_items, angle, offset in [(board.graphicItems, 0, cq.Vector(0, 0, 0))] + [
    (
        getattr(fp, "graphicItems", []),
        fp.position.angle or 0,
        cq.Vector(fp.position.X, -fp.position.Y, 0),
    )
    for fp in board.footprints
]:
    layer_edges = defaultdict(list)
    for item in graphic_items:
        # we only use user layers for case generation, so no need to waste time with others
        if item.layer.startswith("User") and item.layer[-1].isdigit():
            layer_edges[item.layer].extend(
                e.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), angle).translate(offset)
                for e in item_to_edges(item)
            )

    for layer, edges in layer_edges.items():
        wires = normalize_wires(edgesToWires(edges))
        layer_wires[layer].extend(wires)

for layer, wires in layer_wires.items():
    open_wire_count = sum(not wire.wrapped.Closed() for wire in wires)
    if open_wire_count:
        print(
            f"warning: {layer} has {open_wire_count} open wire(s); "
            "open wires are kept; face/offset operations may fail",
            file=sys.stderr,
        )

# Build 3D plates based on extracted edges and specified dimensions --------------------------------

CUT_TOLERANCE = 0.127
PRINT_TOLERANCE = 0.2
PCB_THICKNESS = 1.6
PLATE_BOTTOM_THICKNESS = 2
PLATE_TOP_SOLAR_THICKNESS = 5.03
PLATE_TOP_COVER_THICKNESS = 0.8
PLATE_TOP_SWITCH_THICKNESS = 1.3
PLATE_TOP_SPACER_THICKNESS = 0.9
SKIRT_THICKNESS = 2
TOP_FILLET_RADIUS = 1

bottom_face = cq.Workplane("XY").sketch()
for wire in layer_wires.get("User.7", []):
    bottom_face.face(wire)
for wire in layer_wires.get("User.8", []):
    bottom_face.face(wire, mode="s")

# footprint cutouts (e.g kailh hotswap sockets)
for wire in layer_wires.get("User.6", []):
    for offset_wire in wire.offset2D(CUT_TOLERANCE):
        bottom_face.face(offset_wire, mode="s")

bottom_profile = bottom_face.finalize()
bottom_plate = bottom_profile.extrude(PLATE_BOTTOM_THICKNESS)

top_cut_layers = (
    ("User.5", PLATE_TOP_SPACER_THICKNESS),
    ("User.4", PLATE_TOP_SWITCH_THICKNESS),
    ("User.3", PLATE_TOP_COVER_THICKNESS),
)
top_fill_layers = (("User.2", PLATE_TOP_SOLAR_THICKNESS),)
skirt_height = PLATE_BOTTOM_THICKNESS + PCB_THICKNESS + 0.01
top_shell_height = skirt_height + sum(thickness for _, thickness in top_cut_layers)

top_plate = cq.Workplane("XY").sketch()
for wire in layer_wires.get("User.7", []):
    for offset_wire in wire.offset2D(SKIRT_THICKNESS):
        top_plate.face(offset_wire)

# extrude the top plate before cutting the feature holes so we can apply fillets to the edges
top_plate = (
    top_plate.finalize()
    .extrude(top_shell_height)
    .faces(">Z")
    .edges()
    .fillet(TOP_FILLET_RADIUS)
)

# cut mounting holes
mounting_holes = cq.Sketch()
for wire in layer_wires.get("User.8", []):
    mounting_holes.face(wire, mode="a")

top_plate = (
    top_plate.faces(">Z")
    .center(0, 0)
    .placeSketch(mounting_holes)
    .cutBlind(top_shell_height)
)

# cutout for PCB body and top plate, leaving skirt that envelops them
outline_sketch = cq.Sketch()
for wire in layer_wires.get("User.7", []):
    for offset_wire in wire.offset2D(PRINT_TOLERANCE):
        outline_sketch.face(offset_wire)
top_plate = (
    top_plate.faces("<Z")
    .center(0, 0)
    .placeSketch(outline_sketch)
    .cutBlind(skirt_height)
)

layer_start = skirt_height
for layer_name, layer_thickness in top_cut_layers:
    if not layer_wires.get(layer_name):
        continue

    feature_sketch = cq.Sketch()
    for wire in layer_wires.get(layer_name, []):
        # we apply a cut tolerance to feature cutouts to ensure parts will fit
        for offset_wire in wire.offset2D(PRINT_TOLERANCE):
            feature_sketch.face(offset_wire, mode="a")
    feature_sketch.clean()

    layer_top = layer_start + layer_thickness
    offset_from_top = -(top_shell_height - layer_top)
    top_plate = (
        top_plate.faces(">Z")
        .workplane(offset=offset_from_top)
        .placeSketch(feature_sketch)
        .cutBlind(-layer_thickness)
    )
    layer_start += layer_thickness

for layer_name, layer_thickness in top_fill_layers:
    if not layer_wires.get(layer_name):
        continue

    feature_sketch = cq.Sketch()
    for wire in layer_wires.get(layer_name, []):
        for offset_wire in wire.offset2D(-PRINT_TOLERANCE):
            feature_sketch.face(offset_wire, mode="a")
    feature_sketch.clean()

    top_plate = (
        top_plate.faces(">Z")
        .workplane()
        .center(0, 0)
        .placeSketch(feature_sketch)
        .extrude(layer_thickness)
    )

top_plate_right = top_plate
top_plate_left = top_plate_right.mirror("YZ")

case_dir = cwd / "case"
case_dir.mkdir(parents=True, exist_ok=True)
bottom_profile.export(str(case_dir / "bottom_plate.dxf"))
cq.exporters.export(bottom_plate, str(case_dir / "bottom_plate.step"))
cq.exporters.export(top_plate_right, str(case_dir / "top_plate.step"))
cq.exporters.export(top_plate_right, str(case_dir / "top_plate_right.step"))
cq.exporters.export(top_plate_left, str(case_dir / "top_plate_left.step"))

# Load PCB assembly if present
pcb_assembly_path = case_dir / "cweep.step"
pcb_assembly = None
if pcb_assembly_path.exists():
    pcb_assembly = cq.importers.importStep(str(pcb_assembly_path))
    # the model's z-origin is set based on the bottom of the PCB body, not the PCB solder mask or
    # copper layers between, so we lift it up by the thickness of those other layers
    pcb_assembly = pcb_assembly.translate((0, 0, PLATE_BOTTOM_THICKNESS + 0.05))

if args.preview:
    show(
        bottom_plate,
        pcb_assembly,
        top_plate_right,
        colors=[
            "#707070",
            "#ffc731",
            "#5994dc",
        ],
    )
