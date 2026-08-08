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
from collections import defaultdict
from typing import cast
from math import sqrt
from pathlib import Path

import cadquery as cq
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

# Transform PCB geometry to CadQuery sketches ------------------------------------------------------


def _fix_offset_edges(wire: cq.Wire):
    """Return *wire* with any ``OffsetCurve`` edges replaced by B-splines.

    ``Wire.offset2D`` can produce edges whose underlying geometry is an ``OffsetCurve`` (curve type
    7).  The OCC STEP exporter silently drops any face whose boundary contains such an edge.

    Uses ``GeomAPI_PointsToBSpline`` (OCCT's canonical curve-to-BSpline converter) to approximate
    each OffsetCurve edge as a B-spline.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.GeomAbs import GeomAbs_C2, GeomAbs_OffsetCurve
    from OCP.TColgp import TColgp_HArray1OfPnt

    if not any(
        BRepAdaptor_Curve(e.wrapped).GetType() == GeomAbs_OffsetCurve
        for e in wire.Edges()
    ):
        return wire

    new_edges = []
    for edge in wire.Edges():
        adaptor = BRepAdaptor_Curve(edge.wrapped)
        if adaptor.GetType() != GeomAbs_OffsetCurve:
            new_edges.append(edge.wrapped)
            continue
        u0, u1 = adaptor.FirstParameter(), adaptor.LastParameter()
        n = max(10, int(edge.Length() / 0.5))
        pts = TColgp_HArray1OfPnt(1, n)
        for j in range(n):
            pts.SetValue(j + 1, adaptor.Value(u0 + (u1 - u0) * j / (n - 1)))
        approx = GeomAPI_PointsToBSpline(pts, 1, 8, GeomAbs_C2, 0.001)
        if approx.IsDone():
            p0 = adaptor.Value(u0)
            p1 = adaptor.Value(u1)
            new_edges.append(BRepBuilderAPI_MakeEdge(approx.Curve(), p0, p1).Edge())
        else:
            new_edges.append(edge.wrapped)

    builder = BRepBuilderAPI_MakeWire()
    for e in new_edges:
        builder.Add(e)
    builder.Build()
    return cq.Wire.cast(builder.Wire())


def offset_profile(sketch: cq.Sketch, amount: float):
    """Return a fresh sketch containing the offset of each face in *sketch*.

    Moves each face to the origin before extracting wires so that
    ``Wire.offset2D`` operates on geometry that is centred at (0,0).
    This works around an OCC kernel bug where offsetting a circle wire
    that carries a non-identity ``TopLoc_Location`` doubles the centre
    point.  See CadQuery issues #896, #2046.
    """
    source = sketch.copy().reset().clean()
    source_faces = source.faces().vals()
    if not source_faces:
        return source

    result = cq.Sketch()
    for source_face in source_faces:
        source_normal_z = source_face.normalAt().z
        centre = source_face.Center()
        to_origin = cq.Location(cq.Vector(-centre.x, -centre.y, 0))
        back = cq.Location(cq.Vector(centre.x, centre.y, 0))

        face_at_origin = source_face.moved(to_origin)

        for offset_wire in face_at_origin.outerWire().offset2D(amount):
            offset_wire = _fix_offset_edges(offset_wire)
            offset_face = cq.Face.makeFromWires(offset_wire).moved(back)
            if offset_face.normalAt().z * source_normal_z < 0:
                offset_face = offset_face.reverse()
            result = result.face(offset_face, mode="a")

        for inner_wire in face_at_origin.innerWires():
            for offset_wire in inner_wire.offset2D(-amount):
                offset_wire = _fix_offset_edges(offset_wire)
                offset_face = cq.Face.makeFromWires(offset_wire).moved(back)
                if offset_face.normalAt().z * source_normal_z < 0:
                    offset_face = offset_face.reverse()
                result = result.face(offset_face, mode="s")

    return result.clean().reset()


def add_item_to_sketch(sketch: cq.Sketch, item):
    # KiCad names graphic items as GrXxx (board) or FpXxx (footprint); strip the 2-char prefix.
    shape = item.__class__.__name__[2:]
    if shape == "Line":
        return sketch.segment(
            cq.Vector(item.start.X, item.start.Y, 0),
            cq.Vector(item.end.X, item.end.Y, 0),
        )
    if shape == "Curve":
        return sketch.bezier([cq.Vector(pt.X, pt.Y, 0) for pt in item.coordinates])
    if shape == "Poly":
        return sketch.polygon([cq.Vector(pt.X, pt.Y, 0) for pt in item.coordinates])
    if shape == "Arc":
        return sketch.arc(
            cq.Vector(item.start.X, item.start.Y, 0),
            cq.Vector(item.mid.X, item.mid.Y, 0),
            cq.Vector(item.end.X, item.end.Y, 0),
        )
    if shape == "Rect":
        center = cq.Vector(
            (item.start.X + item.end.X) / 2, (item.start.Y + item.end.Y) / 2, 0
        )
        return (
            sketch.push([center])
            .rect(abs(item.end.X - item.start.X), abs(item.end.Y - item.start.Y))
            .reset()
        )
    if shape == "Circle":
        dx = item.end.X - item.center.X
        dy = item.end.Y - item.center.Y
        return (
            sketch.push([cq.Vector(item.center.X, item.center.Y, 0)])
            .circle(sqrt(dx * dx + dy * dy))
            .reset()
        )
    return sketch


BOARD_FEATURE_NAME = "board_features"

FEATURE_NAME_BY_LIB_ID = {
    "cweep:SM141K04LV": "solar_cell",
    "cweep:MountingHole_2.2mm_M2_DIN965_Pad": "mounting_holes",
    "cweep:SW_Hotswap_Kailh_Choc_V1_1.00u_Reversible": "kailh_switches",
    "cweep:BatteryHolder_Keystone_230-1_1x10440": "battery_cutout",
    "cweep:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder": "capacitors",
    "cweep:D_SOD-123_Reversible": "diodes",
    "cweep:L_Abracon_ASPI-4030S_Reversible": "inductors",
    "cweep:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder": "resistors",
    "cweep:SolderJumper-3_P2.0mm_Open_TrianglePad1.0x1.5mm_Reversible": "solder_jumpers",
    "cweep:SolderWire-0.127sqmm_1x01_D0.48mm_OD1mm_Relief": "solder_wires",
    "cweep:SW_KAN-15_PHT_Reversible": "power_switch",
    "cweep:SW_TH_Tactile_Omron_B3F-102x_Reversible": "reset_button",
    "cweep:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm": "power_ic",
    "cweep:XIAO-nRF52840_Reversible": "microcontroller",
}

raw_board = Board().from_file(cwd / "cweep.kicad_pcb")
footprints = list(raw_board.footprints)
feature_sketch = {BOARD_FEATURE_NAME: defaultdict(lambda: cq.Sketch())}
footprint_placements = defaultdict(list)

for item in raw_board.graphicItems:
    feature_sketch[BOARD_FEATURE_NAME][item.layer] = add_item_to_sketch(
        feature_sketch[BOARD_FEATURE_NAME][item.layer],
        item,
    )

for footprint in footprints:
    feature_name = FEATURE_NAME_BY_LIB_ID.get(footprint.libId)
    if feature_name is None:
        continue
    # KiCad's Y axis is flipped compared to CadQuery, so we negate the Y coordinate to preserve
    footprint_placements[feature_name].append(
        # orientation.
        cq.Location(
            footprint.position.X,
            -footprint.position.Y,
            0,
            rz=footprint.position.angle or 0,
        )
    )
    if feature_name in feature_sketch:
        continue

    feature_sketch[feature_name] = defaultdict(lambda: cq.Sketch())

    for item in getattr(footprint, "graphicItems", []):
        feature_sketch[feature_name][item.layer] = add_item_to_sketch(
            feature_sketch[feature_name][item.layer],
            item,
        )

    for pad_index, pad in enumerate(getattr(footprint, "pads", [])):
        pad_position = getattr(pad, "position", None) or getattr(pad, "at", None)
        if pad_position is None:
            continue

        # KiCad's Y axis is flipped compared to CadQuery, so we negate the Y coordinate to preserve
        # orientation.
        pad_center = pad_position.X, -pad_position.Y
        if pad.shape == "circle":
            feature_sketch[feature_name]["pads"] = (
                feature_sketch[feature_name]["pads"]
                .push([pad_center])
                .circle(pad.size.X / 2)
                .reset()
            )
        elif pad.shape == "roundrect":
            feature_sketch[feature_name]["pads"] = (
                feature_sketch[feature_name]["pads"]
                .push([pad_center])
                .face(
                    cq.Sketch()
                    .rect(pad.size.X, pad.size.Y, tag="pad")
                    .select("pad")
                    .vertices()
                    .fillet(min(pad.size.X, pad.size.Y) * pad.roundrectRatio)
                    .reset(),
                    angle=pad_position.angle or 0,
                    mode="a",
                )
                .reset()
            )
        drill = getattr(pad, "drill", None)
        # We handle only circular drills for now
        if drill and drill.diameter and not drill.oval:
            feature_sketch[feature_name]["drill"] = (
                feature_sketch[feature_name]["drill"]
                .push([pad_center])
                .circle(drill.diameter / 2)
                .reset()
            )

for feature_name, layers in feature_sketch.items():
    for layer_name, sketch in list(layers.items()):
        # Lines, curves, and arcs added to the sketch are not automatically assembled into faces, so
        # we attempt to assemble them here.
        try:
            layers[layer_name] = sketch.assemble()
        except Exception:
            pass

        # KiCad's Y axis is flipped compared to CadQuery, so we mirror the sketches to preserve
        # orientation. Because this flips the normals of the faces, we also reverse the faces to
        # ensure the normals point in the correct direction.
        layers[layer_name] = sketch.faces("+Z")
        if layers[layer_name]._selection:
            layers[layer_name] = sketch.map(lambda f: f.reverse()).replace()
        layers[layer_name] = layers[layer_name].reset().moved(cq.Location(rx=180))


# Build 3D plates based on extracted edges and specified dimensions --------------------------------

TOLERANCE = 0.2

PCB_THICKNESS = raw_board.general.thickness

PLATE_BOTTOM_THICKNESS = 2
PLATE_TOP_COVER_THICKNESS = 0.8
PLATE_TOP_SWITCH_THICKNESS = 1.3
PLATE_TOP_SPACER_THICKNESS = 0.9
SKIRT_THICKNESS = 2
TOP_FILLET_RADIUS = 1

TOP_CUT_LOWER_THICKNESS = PLATE_TOP_SPACER_THICKNESS + PLATE_TOP_SWITCH_THICKNESS

skirt_height = PLATE_BOTTOM_THICKNESS + PCB_THICKNESS + 0.01
top_shell_height = (
    skirt_height
    + PLATE_TOP_SPACER_THICKNESS
    + PLATE_TOP_SWITCH_THICKNESS
    + PLATE_TOP_COVER_THICKNESS
)

SCREW_LENGTH = 6
INDUCTOR_HEIGHT = 3
MAX_0603_HEIGHT = 1
BATTERY_TAB_WIDTH = 5.08

ORIGIN = cq.Vector(0, 0, 0)
SOLAR_TOP_THICKNESS = 1.13
SOLAR_CELL_THICKNESS = 2.1
SOLAR_TOP_Z = top_shell_height + 4.195
SOLAR_WALL_THICKNESS = 1.112
SOLAR_CEILING_TOP_Z = SOLAR_TOP_Z + SOLAR_TOP_THICKNESS
BATTERY_HEIGHT_ABOVE_TOP_SHELL = 3.905

# from top_shell_height (8.852) to top of solar cell (13.445) is 4.597mm

board_outline_sketch = feature_sketch.get(BOARD_FEATURE_NAME).get("Edge.Cuts")

# =============================================================================
# Build 3D plates
# =============================================================================

top_plate_right = cq.Workplane("XY").tag("base")
bottom_plate = cq.Workplane("XY").tag("base")

# ----------------------------------------------------------------- Plate shells

# --- bottom_plate: board outline -> solid base ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch().push([cq.Location()]).face(board_outline_sketch).clean().reset()
    )
    .extrude(PLATE_BOTTOM_THICKNESS)
)

# --- top_shell: board outline -> main body with skirt ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push([cq.Location()])
        .face(offset_profile(board_outline_sketch, SKIRT_THICKNESS))
        .clean()
        .reset()
    )
    .extrude(top_shell_height)
)
# apply: fillet the top face of the shell
top_plate_right = top_plate_right.faces(">Z").fillet(TOP_FILLET_RADIUS)

# --- inner_clearance: hollow out the skirt area ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push([cq.Location()])
        .face(offset_profile(board_outline_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(skirt_height)
)
# --------------------------------------------------------------- Mounting holes

_mounting_holes_sketch = feature_sketch.get("mounting_holes").get("drill")
_mounting_holes_placements = footprint_placements["mounting_holes"]

# --- drill: holes for heat-set brass inserts in top plate  ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_mounting_holes_placements)
        .face(offset_profile(_mounting_holes_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(SCREW_LENGTH + TOLERANCE - skirt_height)
)

# --- drill: screw holes through bottom plate ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_mounting_holes_placements)
        .face(offset_profile(_mounting_holes_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# --------------------------------------------------------------- Battery cutout

_battery_placements = footprint_placements["battery_cutout"]
_battery_top_sketch = feature_sketch.get("battery_cutout").get("Edge.Cuts").clean()
_battery_bottom_sketch = cq.Sketch().push([(-0.775, -0.025)]).rect(7.75, 44.14).reset()

# --- top: battery cutout through top plate ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch().push(_battery_placements).face(_battery_top_sketch).clean().reset()
    )
    .tag("battery_top_sketch")
    # .cutBlind(top_shell_height - skirt_height)
)

# --- bottom: battery access through bottom plate ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_battery_placements)
        .face(offset_profile(_battery_bottom_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# ------------------------------------------------------------- Kailh switches

_kailh_placements = footprint_placements["kailh_switches"]
_kailh_bottom_sketch = feature_sketch["kailh_switches"]["User.6"]
_kailh_lower_sketch = feature_sketch["kailh_switches"]["User.5"]

# --- lower: wide clearance for switch body ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_kailh_placements)
        .face(offset_profile(_kailh_lower_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_TOP_SPACER_THICKNESS)
)

# --- middle: tighter fit through switch plate layer ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height + PLATE_TOP_SPACER_THICKNESS)
    .placeSketch(
        cq.Sketch()
        .push(_kailh_placements)
        .face(
            offset_profile(
                cq.Sketch().rect(13.8, 13.8).rect(3.0, 17.6).clean(), TOLERANCE
            )
        )
        .clean()
        .reset()
    )
    .cutBlind(PLATE_TOP_SWITCH_THICKNESS)
)

# --- upper: final switch opening with filleted corners ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height + TOP_CUT_LOWER_THICKNESS)
    .placeSketch(
        cq.Sketch()
        .push(_kailh_placements)
        .face(
            offset_profile(
                cq.Sketch()
                .rect(15.0, 15.0, tag="upper")
                .select("upper")
                .vertices()
                .fillet(0.85)
                .reset()
                .rect(3.0, 17.6)
                .clean(),
                TOLERANCE,
            )
        )
        .clean()
        .reset()
    )
    .cutBlind(PLATE_TOP_COVER_THICKNESS)
)

# --- bottom: switch pad relief on bottom plate ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_kailh_placements)
        .face(offset_profile(_kailh_bottom_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# ------------------------------------------------------------ Solar housing

_solar_placements = footprint_placements["solar_cell"]
_solar_main_sketch = cq.Sketch().face(
    feature_sketch["solar_cell"]["F.Fab"]
    .faces(cq.selectors.AreaNthSelector(-1))
    .wires()
    .val()
)

# --- main_body: build solar housing as a standalone solid ---
solar_housing = (
    cq.Workplane("XY")
    .tag("solar_base")
    .workplane(offset=top_shell_height)
    .placeSketch(
        cq.Sketch()
        .push(_solar_placements)
        .face(offset_profile(_solar_main_sketch, SOLAR_WALL_THICKNESS))
        .clean()
        .reset()
    )
    .extrude(SOLAR_CEILING_TOP_Z + SOLAR_CELL_THICKNESS - top_shell_height)
)
# apply: fillet the top face; walls around cutout flush with cell
solar_housing = solar_housing.faces(">Z").fillet(TOP_FILLET_RADIUS)

# Cut a rounded rectangular opening in the front of the solar housing to leave room for the battery
# and a chase for the solar cell wires to the PCB.
front_solar_housing = solar_housing.faces("<Y")
back_solar_housing = solar_housing.faces(">Y")

# The battery opening width is set so that the filleted top corners of the opening meet the inner
# walls of the battery cutout in the top plate below. The gap from the solar housing front face's
# left edge to the battery cutout's left edge determines how much to shrink the opening from each
# side.
battery_cutout_width = front_solar_housing.val().BoundingBox().xlen - 2 * (
    top_plate_right.workplaneFromTagged("battery_top_sketch")
    .val()
    .vertices("<X")
    .val()
    .Center()
    .x
    - front_solar_housing.val().BoundingBox().xmin
)
battery_cutout_center = front_solar_housing.val().BoundingBox().center.z
battery_cutout_height = BATTERY_HEIGHT_ABOVE_TOP_SHELL
battery_cutout_rect_height = top_shell_height + battery_cutout_height - skirt_height

# The wire chase sits above the battery opening, tall enough to bridge from the battery cutout top
# to the solar cell ceiling.
solar_wire_chase_height = SOLAR_CEILING_TOP_Z - top_shell_height - battery_cutout_height

# Narrow the chase by the corner fillet radius on both sides.
solar_wire_chase_width = battery_cutout_width - 2 * battery_cutout_height
# Center the chase vertically between the battery opening top and cell ceiling.
solar_wire_chase_center = (
    top_shell_height + battery_cutout_height + SOLAR_CEILING_TOP_Z
) / 2 - battery_cutout_center


small_gap_between_solar_housing_front_and_battery_edge_cut = (
    front_solar_housing.val().Center().y
    - top_plate_right.workplaneFromTagged("battery_top_sketch")
    .val()
    .vertices("<Y")
    .val()
    .Y
)

solar_housing = cast(
    cq.Workplane,
    front_solar_housing.workplane(
        centerOption="CenterOfBoundBox",
        # We extend the cutout beyond the front face of the solar housing by ~0.175mm, so that this
        # cutout does the work that the battery_top_sketch would do
        offset=small_gap_between_solar_housing_front_and_battery_edge_cut,
    )
    .sketch()
    # align the cutout with the bottom of the solar housing
    .push([(0, skirt_height + battery_cutout_rect_height / 2 - battery_cutout_center)])
    .rect(battery_cutout_width, battery_cutout_rect_height)
    .reset()
    .vertices(">Y")
    .fillet(battery_cutout_height)
    .push([(0, solar_wire_chase_center)])
    .rect(solar_wire_chase_width, solar_wire_chase_height)
    .clean()
    .reset()
    .finalize()
    .tag("solar_housing_battery_cutout"),
)

# --- main_body: solar cell pocket ---
solar_housing = (
    solar_housing.workplaneFromTagged("solar_base")
    .workplane(offset=SOLAR_CEILING_TOP_Z)
    .placeSketch(
        cq.Sketch()
        .push(_solar_placements)
        .face(offset_profile(_solar_main_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(SOLAR_CELL_THICKNESS)
)

top_plate_right = (
    top_plate_right.union(solar_housing)
    # We perform this cutout after union-ing with the rest of the body, so that the cutout can
    # affect the top shell, where a portion of the top shell around the solar circuitry that does
    # not support the solar housing
    .workplaneFromTagged("solar_housing_battery_cutout")
    # cut through front to the back of the solar housing, leaving the solar housing wall intact
    .cutBlind(
        -(
            front_solar_housing.val().distance(back_solar_housing.val())
            + small_gap_between_solar_housing_front_and_battery_edge_cut
            - SOLAR_WALL_THICKNESS
            + TOLERANCE
        )
    )
    # Cut out space for battery tabs, which extend just above the top shell
    .workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        feature_sketch.get("battery_cutout").get("F.CrtYd").moved(_battery_placements)
    )
    .cutBlind(BATTERY_TAB_WIDTH - PCB_THICKNESS + TOLERANCE)
)

# ---------------------------------------------------------------- Inductors

_inductors_placements = footprint_placements["inductors"]
_inductors_sketch = feature_sketch["inductors"]["F.CrtYd"]

# --- top: inductor clearance ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_inductors_placements)
        .face(offset_profile(_inductors_sketch, 2 * TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(INDUCTOR_HEIGHT + TOLERANCE)
)

# ---------------------------------------------------------------- 0603 Components

_0603_placements = (
    footprint_placements["capacitors"] + footprint_placements["resistors"]
)
_0603_sketch = feature_sketch["capacitors"]["User.5"]


# --- body: capacitor clearance on top plate ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_0603_placements)
        .face(offset_profile(_0603_sketch, 2 * TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(MAX_0603_HEIGHT + TOLERANCE)
)

# --- body: capacitor clearance on bottom plate ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_0603_placements)
        .face(offset_profile(_0603_sketch, 2 * TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# ------------------------------------------------------------------ Power IC

_power_ic_placements = footprint_placements["power_ic"]
_power_ic_sketch = feature_sketch["power_ic"]["User.5"]

# --- body: power IC clearance on top plate ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_power_ic_placements)
        .face(offset_profile(_power_ic_sketch, 2 * TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(MAX_0603_HEIGHT + TOLERANCE)
)

# --- body: power IC clearance on bottom plate ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_power_ic_placements)
        .face(offset_profile(_power_ic_sketch, 2 * TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# --------------------------------------------------------------- Reset button

_reset_placements = footprint_placements["reset_button"]
_reset_top_sketch = feature_sketch["reset_button"]["User.3"]
_reset_bottom_sketch = feature_sketch.get("reset_button", {}).get("pads")

# --- top: reset button opening ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_reset_placements)
        .face(offset_profile(_reset_top_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(top_shell_height - skirt_height)
)

# --- bottom: reset button pad relief ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_reset_placements)
        .face(offset_profile(_reset_bottom_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# -------------------------------------------------------------- Solder wires

_solder_wires_placements = footprint_placements["solder_wires"]
_solder_wires_sketch = (
    cq.Sketch()
    .push([(0, -2.95)])
    .rect(2.7, 8.6, tag="wire")
    .select("wire")
    .vertices()
    .fillet(1.0)
    .reset()
)

# --- body: solder wire slot ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_solder_wires_placements)
        .face(offset_profile(_solder_wires_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(top_shell_height - skirt_height)
)
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_solder_wires_placements)
        .face(offset_profile(_solder_wires_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# ------------------------------------------------------------ Microcontroller

_mcu_placements = footprint_placements["microcontroller"]
_mcu_lower_sketch = (
    cq.Workplane("XY")
    .sketch()
    .push([(-7.585002, 0.153997), (7.585002, 0.153997)])
    .rect(2.539996, 17.780002, tag="controller_sockets")
    .reset()
    .face(feature_sketch.get("microcontroller").get("F.CrtYd").wires("%CIRCLE").clean())
)
_mcu_upper_sketch = (
    cq.Workplane("XY")
    .center(0, 0.0905)
    .sketch()
    .rect(17.71, 20.955, tag="controller_body")
    .select("controller_body")
    .vertices()
    .fillet(1.905)
)
_mcu_bottom_sketch = (
    cq.Workplane("XY")
    .center(0, 0.0905)
    .sketch()
    .rect(17.71, 20.955)
    .vertices()
    .fillet(1.905)
)

# --- lower: MCU socket cutouts + courtyard ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_mcu_placements)
        .face(offset_profile(_mcu_lower_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(TOP_CUT_LOWER_THICKNESS)
)

# --- upper: MCU body clearance ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height + TOP_CUT_LOWER_THICKNESS)
    .placeSketch(
        cq.Sketch()
        .push(_mcu_placements)
        .face(offset_profile(_mcu_upper_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_TOP_COVER_THICKNESS)
)

# --- bottom: MCU relief on bottom plate ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .placeSketch(
        cq.Sketch()
        .push(_mcu_placements)
        .face(offset_profile(_mcu_bottom_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

# -------------------------------------------------------------- Power switch

_power_switch_arc_radius = sqrt(4.2 * 4.2 + 4.75 * 4.75)
_power_switch_placements = footprint_placements["power_switch"]
_power_switch_top_sketch = (
    cq.Sketch()
    .rect(4.3, 14.8)
    .arc((4.2, 4.75), (0, _power_switch_arc_radius), (-4.2, 4.75))
    .segment((-4.2, -4.75), (-4.2, 4.75))
    .arc((-4.2, -4.75), (0, -_power_switch_arc_radius), (4.2, -4.75))
    .close()
    .assemble()
)
_power_switch_bottom_sketch = feature_sketch["power_switch"]["pads"]

# --- top: power switch opening ---
top_plate_right = (
    top_plate_right.workplaneFromTagged("base")
    .workplane(offset=skirt_height)
    .placeSketch(
        cq.Sketch()
        .push(_power_switch_placements)
        .face(offset_profile(_power_switch_top_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(top_shell_height - skirt_height)
)

# --- bottom: power switch pad relief ---
bottom_plate = (
    bottom_plate.workplaneFromTagged("base")
    .workplane()
    .placeSketch(
        cq.Sketch()
        .push(_power_switch_placements)
        .face(offset_profile(_power_switch_bottom_sketch, TOLERANCE))
        .clean()
        .reset()
    )
    .cutBlind(PLATE_BOTTOM_THICKNESS)
)

top_plate_left = top_plate_right.mirror("YZ")

case_dir = cwd / "case"
case_dir.mkdir(parents=True, exist_ok=True)
cq.exporters.export(bottom_plate.faces("<Z"), str(case_dir / "bottom_plate.dxf"))
cq.exporters.export(bottom_plate, str(case_dir / "bottom_plate.step"))
cq.exporters.export(bottom_plate, str(case_dir / "bottom_plate.stl"))
cq.exporters.export(top_plate_left, str(case_dir / "top_plate_left.step"))
cq.exporters.export(top_plate_left, str(case_dir / "top_plate_left.stl"))
cq.exporters.export(top_plate_right, str(case_dir / "top_plate_right.step"))
cq.exporters.export(top_plate_right, str(case_dir / "top_plate_right.stl"))

# Preview generated plates with PCB assembly if available ------------------------------------------

pcb_assembly_path = case_dir / "cweep.step"
pcb_assembly = None
if pcb_assembly_path.exists():
    pcb_assembly = cq.importers.importStep(str(pcb_assembly_path))
    # the model's z-origin is set based on the bottom of the PCB body, not the PCB solder mask or
    # copper layers between, so we lift it up by the thickness of those other layers
    pcb_assembly = pcb_assembly.translate((0, 0, PLATE_BOTTOM_THICKNESS + 0.05))

mounting_hole_locations = cq.Workplane("XY").pushPoints(
    face.Center()
    for footprint_location in footprint_placements["mounting_holes"]
    for face in feature_sketch["mounting_holes"]["drill"]
    .moved(footprint_location)
    .faces()
    .vals()
)

hardware_instances = []
for model_path, z_min in [
    ("3dmodels/com_mcmaster/91294A004_hex_drive_flat_head_screw_m2x0.4x6.stp", 0),
    ("3dmodels/com_grabcad_shrey.g-2/m2x2x3.2_threaded-insert.step", skirt_height),
]:
    template = cq.importers.importStep(str(cwd / model_path)).val()
    template = template.rotate((0, 0, 0), (1, 0, 0), 180)
    template = template.translate((0, 0, z_min - template.BoundingBox().zmin))
    hardware_instances.append(
        mounting_hole_locations.eachpoint(template, clean=False).combine(clean=False)
    )

preview_objects = [
    bottom_plate,
    top_plate_right,
    pcb_assembly,
    *hardware_instances,
]
preview_colors = [
    "#707070",
    "#5994dc",
    "#ffc731",
    "#ff0000",
    "#00ff00",
]

if args.preview:
    show(*preview_objects, colors=preview_colors)
