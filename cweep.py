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
        if cq.Face.makeFromWires(wire).normalAt().z < 0:
            wire = cq.Shape.cast(wire.wrapped.Reversed())
        normalized.append(wire)
    return normalized


feature_wires = defaultdict(list)
SOLAR_CELL_FOOTPRINT_LIB_ID = "cweep:SM141K04LV"
board = Board().from_file(cwd / "cweep.kicad_pcb")

# Transform board graphics and footprint graphics into board space, but assemble each transformed
# source separately so edgesToWires does not merge unrelated footprint geometry on the same layer.
for graphic_items, angle, offset, lib_id in [
    (board.graphicItems, 0, cq.Vector(0, 0, 0), None)
] + [
    (
        getattr(fp, "graphicItems", []),
        fp.position.angle or 0,
        cq.Vector(fp.position.X, -fp.position.Y, 0),
        getattr(fp, "libId", None),
    )
    for fp in board.footprints
]:
    feature_edges = defaultdict(list)
    solar_cell_fab_source_edges = []
    for item in graphic_items:
        transformed_edges = [
            e.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), angle).translate(offset)
            for e in item_to_edges(item)
        ]
        # we mostly use user layers for case generation, so no need to waste time with others
        if item.layer.startswith("User") and item.layer[-1].isdigit():
            feature_edges[item.layer].extend(transformed_edges)
        # we also extract a solar cell outline to generate the solar cell holder
        #
        # TODO: see where else we can reuse footprint-based geometry like this to avoid having to
        # duplicate graphics on both the board and user layers
        elif lib_id == SOLAR_CELL_FOOTPRINT_LIB_ID and item.layer == "F.Fab":
            feature_edges[SOLAR_CELL_FOOTPRINT_LIB_ID].extend(transformed_edges)

    for feature, edges in feature_edges.items():
        feature_wires[feature].extend(normalize_wires(edgesToWires(edges)))

for feature, wires in feature_wires.items():
    open_wire_count = sum(not wire.wrapped.Closed() for wire in wires)
    if open_wire_count:
        print(
            f"warning: {feature} has {open_wire_count} open wire(s); "
            "open wires are kept; face/offset operations may fail",
            file=sys.stderr,
        )

# Build 3D plates based on extracted edges and specified dimensions --------------------------------

TOLERANCE = 0.2
PCB_THICKNESS = 1.6
PLATE_BOTTOM_THICKNESS = 2
PLATE_TOP_SOLAR_TOP_THICKNESS = 1.13
PLATE_TOP_SOLAR_WALL_THICKNESS = 3.9
PLATE_TOP_COVER_THICKNESS = 0.8
PLATE_TOP_SWITCH_THICKNESS = 1.3
PLATE_TOP_SPACER_THICKNESS = 0.9
SOLAR_CELL_THICKNESS = 2.1
SKIRT_THICKNESS = 2
TOP_FILLET_RADIUS = 1


def offset_wires(wires, offset):
    return [offset_wire for wire in wires for offset_wire in wire.offset2D(offset)]


def profile_from_wires(add_wires=(), sub_wires=(), offset=0):
    sketch = cq.Sketch()
    for wire in add_wires:
        sketch.face(wire, mode="a")
    for wire in sub_wires:
        sketch.face(wire, mode="s")
    sketch.clean()
    return cq.Workplane("XY").workplane(offset=offset).placeSketch(sketch)


top_cut_layers = (
    ("User.5", PLATE_TOP_SPACER_THICKNESS),
    ("User.4", PLATE_TOP_SWITCH_THICKNESS),
    ("User.3", PLATE_TOP_COVER_THICKNESS),
)
top_fill_layers = (
    ("User.2", PLATE_TOP_SOLAR_WALL_THICKNESS),
    ("User.1", PLATE_TOP_SOLAR_TOP_THICKNESS),
)
skirt_height = PLATE_BOTTOM_THICKNESS + PCB_THICKNESS + 0.01
top_shell_height = skirt_height + sum(thickness for _, thickness in top_cut_layers)
solar_ceiling_top_z = (
    top_shell_height + PLATE_TOP_SOLAR_WALL_THICKNESS + PLATE_TOP_SOLAR_TOP_THICKNESS
)

board_outline_wires = feature_wires["User.7"]
mounting_hole_wires = feature_wires["User.8"]
footprint_cutout_wires = offset_wires(feature_wires["User.6"], TOLERANCE)
solar_cell_cutout_wires = offset_wires(feature_wires[SOLAR_CELL_FOOTPRINT_LIB_ID], TOLERANCE)
outer_outline_wires = offset_wires(board_outline_wires, SKIRT_THICKNESS)
inner_outline_wires = offset_wires(board_outline_wires, TOLERANCE)

bottom_profile = profile_from_wires(
    board_outline_wires,
    mounting_hole_wires + footprint_cutout_wires,
)
bottom_plate = bottom_profile.extrude(PLATE_BOTTOM_THICKNESS)


# Build the main top body first, then add the solar fills, fillet that main shell, and cut the
# interior/layer features back out.
top_plate = (
    profile_from_wires(outer_outline_wires)
    .extrude(top_shell_height)
    .faces(">Z")
    .fillet(TOP_FILLET_RADIUS)
    .cut(profile_from_wires(inner_outline_wires).extrude(skirt_height))
)

# These wires are collected while extruding the main solar/battery compartment, so that we can add a
# support rib under the solar cell ceiling, as well as a thin wall around the solar cell, without
# copying those features into yet another user layer
solar_wall_wires = []
solar_top_wires = []
layer_base = top_shell_height
for layer_name, layer_thickness in top_fill_layers:
    layer_offset_wires = offset_wires(feature_wires[layer_name], -TOLERANCE)

    if layer_name == "User.2":
        solar_wall_wires = layer_offset_wires
    elif layer_name == "User.1":
        solar_top_wires = layer_offset_wires

    top_plate = top_plate.union(
        profile_from_wires(layer_offset_wires, offset=layer_base).extrude(
            layer_thickness
        )
    )
    layer_base += layer_thickness

layer_base = skirt_height
for layer_name, layer_thickness in top_cut_layers:
    cut_wires = offset_wires(
        feature_wires[layer_name] + mounting_hole_wires, TOLERANCE
    )
    top_plate = top_plate.cut(
        profile_from_wires(cut_wires, offset=layer_base).extrude(layer_thickness)
    )
    layer_base += layer_thickness

# We protect the edges of the solar cell by adding a thin wall that the cell will sit flush within
solar_cell_wall = profile_from_wires(
    solar_top_wires,
    offset=solar_ceiling_top_z,
).extrude(SOLAR_CELL_THICKNESS)
solar_cell_wall = solar_cell_wall.faces(">Z").fillet(TOP_FILLET_RADIUS)
solar_cell_wall = solar_cell_wall.cut(
    profile_from_wires(
        solar_cell_cutout_wires,
        offset=solar_ceiling_top_z,
    ).extrude(SOLAR_CELL_THICKNESS)
)
top_plate = top_plate.union(solar_cell_wall)

# We add a support rib under the solar cell ceiling that doubles as a holder for the battery below
solar_wall = cq.Workplane().add(solar_wall_wires)
solar_top = cq.Workplane().add(solar_top_wires)
inner_solar_wall_x_edge = (
    solar_wall.edges("%Line and |Y")
    .sort(lambda edge: edge.Length())[-1:]
    .edges(">X")
    .val()
)
inner_solar_wall_y_max = inner_solar_wall_x_edge.vertices(">Y").Center().y + TOLERANCE
inner_solar_wall_y_min = inner_solar_wall_x_edge.vertices("<Y").Center().y
solar_support = (
    cq.Workplane(
        "XZ",
        origin=(
            inner_solar_wall_x_edge.Center().x,
            inner_solar_wall_y_max,
            top_shell_height,
        ),
    )
    .lineTo(0, PLATE_TOP_SOLAR_WALL_THICKNESS)
    .lineTo(PLATE_TOP_SOLAR_WALL_THICKNESS, PLATE_TOP_SOLAR_WALL_THICKNESS)
    .threePointArc(
        (
            PLATE_TOP_SOLAR_WALL_THICKNESS * (1 - 1 / sqrt(2)),
            PLATE_TOP_SOLAR_WALL_THICKNESS / sqrt(2),
        ),
        (0, 0),
    )
    .close()
    .extrude(inner_solar_wall_y_max - inner_solar_wall_y_min)
)

top_plate_right = top_plate.union(solar_support)
top_plate_left = top_plate_right.mirror("YZ")

case_dir = cwd / "case"
case_dir.mkdir(parents=True, exist_ok=True)
bottom_profile.export(str(case_dir / "bottom_plate.dxf"))
cq.exporters.export(bottom_plate, str(case_dir / "bottom_plate.step"))
cq.exporters.export(bottom_plate, str(case_dir / "bottom_plate.stl"))
cq.exporters.export(top_plate_left, str(case_dir / "top_plate_left.step"))
cq.exporters.export(top_plate_left, str(case_dir / "top_plate_left.stl"))
cq.exporters.export(top_plate_right, str(case_dir / "top_plate_right.step"))
cq.exporters.export(top_plate_right, str(case_dir / "top_plate_right.stl"))

# Load PCB assembly if present
pcb_assembly_path = case_dir / "cweep.step"
pcb_assembly = None
if pcb_assembly_path.exists():
    pcb_assembly = cq.importers.importStep(str(pcb_assembly_path))
    # the model's z-origin is set based on the bottom of the PCB body, not the PCB solder mask or
    # copper layers between, so we lift it up by the thickness of those other layers
    pcb_assembly = pcb_assembly.translate((0, 0, PLATE_BOTTOM_THICKNESS + 0.05))

preview_objects = [
    bottom_plate,
    pcb_assembly,
    top_plate_right,
]
preview_colors = [
    "#707070",
    "#ffc731",
    "#5994dc",
]

if args.preview:
    show(*preview_objects, colors=preview_colors)
