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

# Transform PCB geometry to CadQuery wires ---------------------------------------------------------


def kicad_xy(x, y):
    return cq.Vector(x, -y, 0)


def item_to_edges(item):
    """
    Convert a KiCad PCB graphic item to CadQuery edges (Y-axis flipped to match CQ convention).
    """
    vec = lambda position: kicad_xy(position.X, position.Y)
    # KiCad names graphic items as GrXxx (board) or FpXxx (footprint); strip the 2-char prefix.
    shape = item.__class__.__name__[2:]
    if shape == "Line":
        return [
            cq.Edge.makeLine(
                vec(item.start),
                vec(item.end),
            )
        ]
    elif shape == "Curve":
        return [cq.Edge.makeBezier([vec(pt) for pt in item.coordinates])]
    elif shape == "Poly":
        pts = [vec(pt) for pt in item.coordinates]
        return [
            cq.Edge.makeLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))
        ]
    elif shape == "Arc":
        return [
            cq.Edge.makeThreePointArc(
                vec(item.start),
                vec(item.mid),
                vec(item.end),
            )
        ]
    elif shape == "Rect":
        s, e = item.start, item.end
        corners = [
            vec(s),
            kicad_xy(e.X, s.Y),
            vec(e),
            kicad_xy(s.X, e.Y),
        ]
        return [cq.Edge.makeLine(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    elif shape == "Circle":
        dx = item.end.X - item.center.X
        dy = item.end.Y - item.center.Y
        return [cq.Edge.makeCircle(sqrt(dx * dx + dy * dy), vec(item.center))]
    return []


def normalize_wires(wires):
    # Flipping KiCad's Y axis reflects loop winding, so normalize planar wires before sketching.
    normalized = []
    for wire in wires:
        if not wire.wrapped.Closed():
            normalized.append(wire)
            continue

        if cq.Face.makeFromWires(wire).normalAt().z < 0:
            wire = cq.Shape.cast(wire.wrapped.Reversed())
        normalized.append(wire)
    return normalized


def wires_from_edges(edges):
    return normalize_wires(edgesToWires(edges))


BOARD_FEATURE_NAME = "board_features"

FEATURE_NAME_BY_LIB_ID = {
    "cweep:SM141K04LV": "solar_cell",
    "cweep:MountingHole_2.2mm_M2_DIN965_Pad": "mounting_holes",
    "cweep:SW_Hotswap_Kailh_Choc_V1_1.00u_Reversible": "kailh_switches",
    "cweep:BatteryHolder_Keystone_230-1_1x10440": "battery_holder",
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
feature_edges = defaultdict(lambda: defaultdict(list))
feature_local_wire = {}
footprint_placements = defaultdict(list)

for item in raw_board.graphicItems:
    feature_edges[BOARD_FEATURE_NAME][item.layer].extend(item_to_edges(item))

for footprint in footprints:
    feature_name = FEATURE_NAME_BY_LIB_ID.get(footprint.libId)
    if feature_name is None:
        continue
    footprint_angle = footprint.position.angle or 0
    footprint_offset = kicad_xy(footprint.position.X, footprint.position.Y)
    footprint_placements[feature_name].append((footprint_angle, footprint_offset))
    footprint_edges = defaultdict(list)

    for item in getattr(footprint, "graphicItems", []):
        footprint_edges[item.layer].extend(item_to_edges(item))

    for pad in getattr(footprint, "pads", []):
        pad_position = getattr(pad, "position", None) or getattr(pad, "at", None)
        if pad_position is not None and pad.shape == "circle":
            footprint_edges["pads"].append(
                cq.Edge.makeCircle(
                    pad.size.X / 2,
                    kicad_xy(pad_position.X, pad_position.Y),
                )
            )
        elif pad_position is not None and pad.shape == "roundrect":
            pad_edges = (
                cq.Workplane("XY")
                .sketch()
                .rect(pad.size.X, pad.size.Y)
                .vertices()
                .fillet(min(pad.size.X, pad.size.Y) * pad.roundrectRatio)
                .faces()
                .wires()
                .val()
                .Edges()
            )
            pad_angle = pad_position.angle or 0
            if pad_angle:
                pad_edges = [
                    edge.rotate(
                        cq.Vector(0, 0, 0),
                        cq.Vector(0, 0, 1),
                        pad_angle,
                    )
                    for edge in pad_edges
                ]
            footprint_edges["pads"].extend(
                [edge.translate(kicad_xy(pad_position.X, pad_position.Y)) for edge in pad_edges]
            )
        drill = getattr(pad, "drill", None)
        # We handle only circular drills for now
        if (
            pad_position is None
            or drill is None
            or drill.diameter is None
            or drill.oval
        ):
            continue
        footprint_edges["drill"].append(
            cq.Edge.makeCircle(
                drill.diameter / 2,
                kicad_xy(pad_position.X, pad_position.Y),
            )
        )

    if feature_name not in feature_local_wire:
        feature_local_wire[feature_name] = {
            layer_name: wires_from_edges(edges)
            for layer_name, edges in footprint_edges.items()
        }

    for layer_name, layer_edges in footprint_edges.items():
        feature_edges[feature_name][layer_name].extend(
            [
                edge.rotate(
                    cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), footprint_angle
                ).translate(footprint_offset)
                for edge in layer_edges
            ]
        )

feature_wire = {
    feature_name: {
        layer_name: wires_from_edges(edges)
        for layer_name, edges in feature_layers.items()
    }
    for feature_name, feature_layers in feature_edges.items()
}


# Build 3D plates based on extracted edges and specified dimensions --------------------------------


TOLERANCE = 0.2
PCB_THICKNESS = 1.6
PLATE_BOTTOM_THICKNESS = 2
PLATE_TOP_COVER_THICKNESS = 0.8
PLATE_TOP_SWITCH_THICKNESS = 1.3
PLATE_TOP_SPACER_THICKNESS = 0.9
SKIRT_THICKNESS = 2
TOP_FILLET_RADIUS = 1
POWER_SWITCH_ARC_RADIUS = sqrt(4.2 * 4.2 + 4.75 * 4.75)

TOP_CUT_TOTAL_THICKNESS = (
    PLATE_TOP_SPACER_THICKNESS
    + PLATE_TOP_SWITCH_THICKNESS
    + PLATE_TOP_COVER_THICKNESS
)
TOP_CUT_LOWER_THICKNESS = PLATE_TOP_SPACER_THICKNESS + PLATE_TOP_SWITCH_THICKNESS

skirt_height = PLATE_BOTTOM_THICKNESS + PCB_THICKNESS + 0.01
top_shell_height = skirt_height + TOP_CUT_TOTAL_THICKNESS

# TODO: build this as a single fluent API call, without unioning separate extrusions. When you're
# done with one layer, just put a sketch on the top face and extrude the next.
def build_kailh_switches_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(14.5, 13.8)
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
        .union(
            cq.Workplane("XY")
            .workplane(offset=skirt_height + PLATE_TOP_SPACER_THICKNESS)
            .sketch()
            .rect(13.8, 13.8)
            .rect(3.0, 17.6, mode="a")
            .faces()
            .wires()
            .offset(TOLERANCE)
            .finalize()
            .extrude(PLATE_TOP_SWITCH_THICKNESS),
            clean=False,
        )
        .union(
            cq.Workplane("XY")
            .workplane(offset=skirt_height + TOP_CUT_LOWER_THICKNESS)
            .sketch()
            .rect(15.0, 15.0, tag="upper")
            .select("upper")
            .vertices()
            .fillet(0.85)
            .reset()
            .rect(3.0, 17.6, mode="a")
            .faces()
            .wires()
            .offset(TOLERANCE)
            .finalize()
            .extrude(PLATE_TOP_COVER_THICKNESS),
            clean=False,
        )
    )


def build_battery_holder_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(2.47125, 0)
        .sketch()
        # main battery cutout
        .rect(16.3425, 45.505)
        # cutouts for battery contacts
        .push([(5.17, 0)])
        .rect(6.0025, 40.4, mode="s")
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )

def build_battery_holder_bottom_cutout():
    return (
        cq.Workplane("XY")
        .center(-0.775, -0.025)
        .sketch()
        .rect(7.75, 44.14)
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_BOTTOM_THICKNESS)
    )


def build_inductors_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(4.6, 4.5)
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )


def build_capacitors_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(0.001632, -0.003268)
        .sketch()
        .rect(2.8, 0.95)
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
    )

def build_resistors_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(2.8, 0.95)
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
    )

def build_power_ic_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(3.8, 3.8)
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
    )

def build_reset_button_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(3.25, -2.25)
        .sketch()
        .rect(7.5, 6.0)
        .vertices()
        .fillet(0.5)
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )


def build_reset_button_bottom_cutout():
    sketch = cq.Sketch()
    for pad_wire in feature_local_wire.get("reset_button", {}).get("pads", []):
        sketch.face(pad_wire, mode="a")
    return cq.Workplane("XY").placeSketch(sketch).extrude(PLATE_BOTTOM_THICKNESS)


def build_solder_wires_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(0, -2.95)
        .sketch()
        .rect(2.7, 8.6)
        .vertices()
        .fillet(1.0)
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )

def build_microcontroller_cutout():
    lower_stage = (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .push([(-7.585002, 0.153997), (7.585002, 0.153997)])
        .rect(2.539996, 17.780002, tag="controller_sockets")
        .select("controller_sockets")
        .wires()
        .offset(TOLERANCE)
        .reset()
    )
    # We cut holes for the pogo pins for the battery and reset pins
    for courtyard_wire in feature_local_wire.get("microcontroller", {}).get(
        "F.CrtYd", []
    ):
        if (
            len(courtyard_wire.Edges()) != 1
            or courtyard_wire.Edges()[0].geomType() != "CIRCLE"
        ):
            continue
        lower_stage = (
            lower_stage.push([(courtyard_wire.Center().x, courtyard_wire.Center().y)])
            .circle(
                (courtyard_wire.BoundingBox().xmax - courtyard_wire.BoundingBox().xmin)
                / 2
                + TOLERANCE,
                mode="a",
            )
            .reset()
        )
    lower_cutout = lower_stage.finalize().extrude(TOP_CUT_LOWER_THICKNESS)
    upper_cutout = (
        cq.Workplane("XY")
        .workplane(offset=skirt_height + TOP_CUT_LOWER_THICKNESS)
        .center(0, 0.0905)
        .sketch()
        .rect(17.71, 20.955, tag="controller_body")
        .select("controller_body")
        .vertices()
        .fillet(1.905)
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_COVER_THICKNESS)
    )
    return lower_cutout.union(upper_cutout, clean=False)


def build_microcontroller_bottom_cutout():
    return (
        cq.Workplane("XY")
        .center(0, 0.0905)
        .sketch()
        .rect(17.71, 20.955)
        .vertices()
        .fillet(1.905)
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_BOTTOM_THICKNESS)
    )

def build_power_switch_cutout():
    sketch = (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(8.4, 9.5)
        .rect(4.3, 14.8, mode="a")
    )
    for y_sign in [1, -1]:
        arc = (
            cq.Workplane("XY")
            .moveTo(-4.2, y_sign * 4.75)
            .lineTo(4.2, y_sign * 4.75)
            .threePointArc((0, y_sign * POWER_SWITCH_ARC_RADIUS), (-4.2, y_sign * 4.75))
            .close()
            .val()
        )
        sketch = sketch.face(arc, mode="a")
    return (
        sketch.faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )

def build_power_switch_bottom_cutout():
    power_switch_pads = feature_local_wire.get("power_switch").get("pads", [])
    return (
        cq.Workplane("XY")
        .sketch()
        .face(power_switch_pads[0], mode="a")
        .face(power_switch_pads[1], mode="a")
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_BOTTOM_THICKNESS)
    )


def build_board_cutout():
    body = (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(27.40125, -49.7)
        .sketch()
        .rect(6.0025, 40.4)
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
    )
    tabs = (
        cq.Workplane("XY")
        .workplane(offset=skirt_height + PLATE_TOP_SPACER_THICKNESS)
        .center(27.40125, -49.7)
        .sketch()
        .push([(0, 19.10125), (0, -19.10125)])
        .rect(6.0025, 2.1975)
        .faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SWITCH_THICKNESS + PLATE_TOP_COVER_THICKNESS)
    )
    return body.union(tabs, clean=False)


def build_bottom_cutout_from_top(top_cutout):
    lowered_top_cutout = cq.Workplane().add(
        top_cutout.val().translate((0, 0, -skirt_height))
    )
    sketch = cq.Workplane("XY").sketch()
    for face in lowered_top_cutout.faces("<Z").vals():
        sketch = sketch.face(face.outerWire(), mode="a")
        for inner_wire in face.innerWires():
            sketch = sketch.face(inner_wire, mode="s")
    return sketch.finalize().extrude(PLATE_BOTTOM_THICKNESS)

def build_inductors_bottom_cutout():
    return None


def build_kailh_switches_bottom_cutout():
    front_fab_wires = feature_local_wire.get("kailh_switches", {}).get("F.Fab", [])
    back_fab_wires = feature_local_wire.get("kailh_switches", {}).get("B.Fab", [])
    drill_wires = feature_local_wire.get("kailh_switches", {}).get("drill", [])
    # the F.Fab layer also has a square wire around the whole switch footprint
    front_socket_wire = min(
        front_fab_wires,
        key=lambda wire: cq.Face.makeFromWires(wire).Area(),
    )
    back_socket_wire = back_fab_wires[0]

    drill_points_by_radius = defaultdict(list)
    for drill_wire in drill_wires:
        drill_bb = drill_wire.BoundingBox()
        drill_radius = round((drill_bb.xmax - drill_bb.xmin) / 2 + TOLERANCE, 6)
        drill_points_by_radius[drill_radius].append(
            (drill_wire.Center().x, drill_wire.Center().y)
        )

    (
        guide_hole_radius,
        top_contact_radius,
        lower_socket_radius,
        center_hole_radius,
    ) = sorted(drill_points_by_radius)
    guide_hole_points = sorted(drill_points_by_radius[guide_hole_radius])
    top_contact_points = sorted(drill_points_by_radius[top_contact_radius])
    lower_socket_points = sorted(drill_points_by_radius[lower_socket_radius])
    center_hole_points = drill_points_by_radius[center_hole_radius]

    top_y = max(wire.Center().y for wire in drill_wires)
    top_drill_wires = sorted(
        [wire for wire in drill_wires if abs(wire.Center().y - top_y) < 1e-6],
        key=lambda wire: wire.Center().x,
    )
    bridge_specs = []
    for top_drill_wire in [top_drill_wires[0], top_drill_wires[-1]]:
        top_drill_bb = top_drill_wire.BoundingBox()
        socket_wire = min(
            [back_socket_wire, front_socket_wire],
            key=lambda wire: abs(wire.Center().x - top_drill_wire.Center().x),
        )
        socket_top_y = socket_wire.BoundingBox().ymax
        bridge_specs.append(
            (
                (
                    top_drill_wire.Center().x,
                    (top_drill_wire.Center().y + socket_top_y) / 2,
                ),
                top_drill_bb.xmax - top_drill_bb.xmin + 2 * TOLERANCE,
                top_drill_wire.Center().y - socket_top_y + 2 * TOLERANCE,
            )
        )

    return (
        cq.Workplane("XY")
        .sketch()
        .face(back_socket_wire, mode="a")
        .face(front_socket_wire, mode="a")
        .push(top_contact_points)
        .circle(top_contact_radius, mode="a")
        .push(lower_socket_points)
        .circle(lower_socket_radius, mode="a")
        .push(center_hole_points)
        .circle(center_hole_radius, mode="a")
        .push(guide_hole_points)
        .circle(guide_hole_radius, mode="a")
        .push([bridge_specs[0][0]])
        .rect(bridge_specs[0][1], bridge_specs[0][2], mode="a")
        .push([bridge_specs[1][0]])
        .rect(bridge_specs[1][1], bridge_specs[1][2], mode="a")
        .finalize()
        .extrude(PLATE_BOTTOM_THICKNESS)
    )

def build_top_solar_component():
    solar_wall_thickness = 3.9
    solar_top_thickness = 1.13
    solar_cell_thickness = 2.1
    solar_top_z = top_shell_height + solar_wall_thickness
    solar_ceiling_top_z = solar_top_z + solar_top_thickness
    battery_holder_wall_left_x = 21.73 - 15.34 / 2
    battery_holder_top_y = -49.7 + 45.505 / 2

    solar_wall = (
        cq.Workplane("XY")
        .workplane(offset=top_shell_height)
        .sketch()
        .push([(20.5375, -48.7)])
        .rect(17.725, 47.505, tag="solar_outer")
        .select("solar_outer")
        .vertices("<X and >Y")
        .fillet(2.0)
        .reset()
        .push([(21.73, -49.7)])
        .rect(15.34, 45.505, mode="s")
        .reset()
        .push([(26.9, -49.7)])
        .rect(5.0, 36.005, mode="a")
        .faces()
        .wires()
        .offset(-TOLERANCE)
        .finalize()
        .extrude(solar_wall_thickness)
    )
    solar_top = (
        cq.Workplane("XY")
        .workplane(offset=solar_top_z)
        .sketch()
        .push([(20.5375, -48.7)])
        .rect(17.725, 47.505, tag="solar_outer")
        .select("solar_outer")
        .vertices("<X and >Y")
        .fillet(2.0)
        .reset()
        .push([(21.18, -49.92125)])
        .rect(6.44, 45.0625, mode="s")
        .reset()
        .push([(26.9, -70.0775)])
        .rect(5.0, 4.75, mode="s")
        .faces()
        .wires()
        .offset(-TOLERANCE)
        .finalize()
        .extrude(solar_top_thickness)
    )
    solar_cell_guard = (
        cq.Workplane("XY")
        .workplane(offset=solar_ceiling_top_z)
        .sketch()
        .push([(20.5375, -48.7)])
        .rect(17.725, 47.505, tag="solar_outer")
        .select("solar_outer")
        .vertices("<X and >Y")
        .fillet(2.0)
        .reset()
        .push([(21.18, -49.92125)])
        .rect(6.44, 45.0625, mode="s")
        .reset()
        .push([(26.9, -70.0775)])
        .rect(5.0, 4.75, mode="s")
        .faces()
        .wires()
        .offset(-TOLERANCE)
        .finalize()
        .extrude(solar_cell_thickness)
        .faces(">Z")
        .fillet(TOP_FILLET_RADIUS)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=solar_ceiling_top_z)
            .sketch()
            .face(feature_wire.get("solar_cell").get("F.Fab", [])[0], mode="a")
            .wires()
            .offset(TOLERANCE)
            .finalize()
            .extrude(solar_cell_thickness)
        )
    )

    return (
        # The main solar cell wall that extends up from the top plate and wraps around the battery
        solar_wall
        # We add a support rib under the solar cell ceiling that doubles as a holder for the battery
        # below
        .union(
            cq.Workplane(
                "XZ",
                origin=(
                    battery_holder_wall_left_x - TOLERANCE,
                    battery_holder_top_y + TOLERANCE,
                    top_shell_height,
                ),
            )
            .lineTo(0, solar_wall_thickness)
            .lineTo(solar_wall_thickness, solar_wall_thickness)
            .threePointArc(
                (
                    solar_wall_thickness * (1 - 1 / sqrt(2)),
                    solar_wall_thickness / sqrt(2),
                ),
                (0, 0),
            )
            .close()
            .extrude(45.505 + TOLERANCE)
        )
        # The face that the solar cell rests on top of, leaving a rectangular hole for the wires to
        # exit the cell and run down to the pcb
        .union(solar_top)
        # We protect the edges of the solar cell with a thin, filleted wall that the cell will sit
        # flush within
        .union(solar_cell_guard)
    )

def build_mounting_holes_cutout():
    sketch = cq.Workplane("XY").workplane(offset=skirt_height).sketch()
    for wire in feature_wire.get("mounting_holes").get("drill", []):
        sketch = sketch.face(wire, mode="a")
    return (
        sketch.faces()
        .wires()
        .offset(TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_LOWER_THICKNESS)
    )

board_outline_candidates = [
    wire
    for wire in feature_wire.get(BOARD_FEATURE_NAME).get("Edge.Cuts", [])
    if wire.wrapped.Closed()
]
board_outline_wires = [
    max(board_outline_candidates, key=lambda wire: cq.Face.makeFromWires(wire).Area())
] if board_outline_candidates else []
outer_outline_wires = [
    offset_wire
    for wire in board_outline_wires
    for offset_wire in wire.offset2D(SKIRT_THICKNESS)
]
inner_outline_wires = [
    offset_wire
    for wire in board_outline_wires
    for offset_wire in wire.offset2D(TOLERANCE)
]


def build_bottom_plate_body():
    sketch = cq.Sketch()
    for wire in board_outline_wires:
        sketch.face(wire, mode="a")
    return cq.Workplane("XY").placeSketch(sketch).extrude(PLATE_BOTTOM_THICKNESS)

def build_top_plate_body():
    outer_sketch = cq.Workplane("XY").sketch()
    for wire in outer_outline_wires:
        outer_sketch = outer_sketch.face(wire, mode="a")
    inner_sketch = cq.Workplane("XY").sketch()
    for wire in inner_outline_wires:
        inner_sketch = inner_sketch.face(wire, mode="a")
    return (
        outer_sketch.finalize()
        .extrude(top_shell_height)
        .faces(">Z")
        .fillet(TOP_FILLET_RADIUS)
        .cut(inner_sketch.finalize().extrude(skirt_height))
        .union(build_top_solar_component())
    )



def transform_cutout(cutout, footprint_angle, footprint_offset):
    return cutout.rotate((0, 0, 0), (0, 0, 1), footprint_angle).translate(
        (footprint_offset.x, footprint_offset.y, footprint_offset.z)
    )


top_plate_right = build_top_plate_body().cut(build_board_cutout())
for feature_name in sorted(footprint_placements):
    build_top_cutout = globals().get(f"build_{feature_name}_cutout")
    if build_top_cutout is None:
        continue

    cutout = build_top_cutout()
    if cutout is None:
        continue

    for footprint_angle, footprint_offset in footprint_placements[feature_name]:
        top_plate_right = top_plate_right.cut(
            transform_cutout(cutout, footprint_angle, footprint_offset)
        )

bottom_plate = build_bottom_plate_body()
for feature_name in sorted(footprint_placements):
    build_bottom_cutout = globals().get(f"build_{feature_name}_bottom_cutout")
    if build_bottom_cutout is None:
        build_top_cutout = globals().get(f"build_{feature_name}_cutout")
        if build_top_cutout is None:
            continue
        cutout = build_bottom_cutout_from_top(build_top_cutout())
    else:
        cutout = build_bottom_cutout()

    if cutout is None:
        continue

    for footprint_angle, footprint_offset in footprint_placements[feature_name]:
        bottom_plate = bottom_plate.cut(
            transform_cutout(cutout, footprint_angle, footprint_offset)
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

# Load PCB assembly if present
pcb_assembly_path = case_dir / "cweep.step"
pcb_assembly = None
if pcb_assembly_path.exists():
    pcb_assembly = cq.importers.importStep(str(pcb_assembly_path))
    # the model's z-origin is set based on the bottom of the PCB body, not the PCB solder mask or
    # copper layers between, so we lift it up by the thickness of those other layers
    pcb_assembly = pcb_assembly.translate((0, 0, PLATE_BOTTOM_THICKNESS + 0.05))

mounting_hole_locations = cq.Workplane("XY").pushPoints(
    wire.Center() for wire in feature_wire.get("mounting_holes").get("drill", [])
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
    # pcb_assembly,
    top_plate_right,
    # *hardware_instances,
]
preview_colors = [
    "#707070",
    # "#ffc731",
    "#5994dc",
    # "#ff0000",
    # "#00ff00",
]

if args.preview:
    show(*preview_objects, colors=preview_colors)
