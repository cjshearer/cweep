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


def kicad_xy(x, y):
    return cq.Vector(x, -y, 0)


def add_item_to_sketch(sketch: cq.Sketch, item):
    """
    Add a KiCad PCB graphic item to a CadQuery sketch (Y-axis flipped to match CQ convention).
    """
    vec = lambda position: kicad_xy(position.X, position.Y)
    # KiCad names graphic items as GrXxx (board) or FpXxx (footprint); strip the 2-char prefix.
    shape = item.__class__.__name__[2:]
    if shape == "Line":
        return sketch.segment(vec(item.start), vec(item.end))
    if shape == "Curve":
        return sketch.bezier([vec(pt) for pt in item.coordinates])
    if shape == "Poly":
        pts = [vec(pt) for pt in item.coordinates]
        return sketch.polygon(pts).reset()
    if shape == "Arc":
        return sketch.arc(vec(item.start), vec(item.mid), vec(item.end))
    if shape == "Rect":
        center = kicad_xy(
            (item.start.X + item.end.X) / 2,
            (item.start.Y + item.end.Y) / 2,
        )
        return (
            sketch.push([center])
            .rect(abs(item.end.X - item.start.X), abs(item.end.Y - item.start.Y))
            .reset()
        )
    if shape == "Circle":
        dx = item.end.X - item.center.X
        dy = item.end.Y - item.center.Y
        return sketch.push([vec(item.center)]).circle(sqrt(dx * dx + dy * dy)).reset()
    return sketch

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
    footprint_placements[feature_name].append(
        (
            footprint.position.angle or 0,
            kicad_xy(footprint.position.X, footprint.position.Y),
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

        pad_center = kicad_xy(pad_position.X, pad_position.Y)
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
        try:
            layers[layer_name] = sketch.assemble()
        except Exception:
            pass

# Build 3D plates based on extracted edges and specified dimensions --------------------------------


TOLERANCE = 0.2
PCB_THICKNESS = 1.6
PLATE_BOTTOM_THICKNESS = 2
PLATE_TOP_COVER_THICKNESS = 0.8
PLATE_TOP_SWITCH_THICKNESS = 1.3
PLATE_TOP_SPACER_THICKNESS = 0.9
SCREW_LENGTH = 6
SKIRT_THICKNESS = 2
TOP_FILLET_RADIUS = 1
POWER_SWITCH_ARC_RADIUS = sqrt(4.2 * 4.2 + 4.75 * 4.75)

TOP_CUT_TOTAL_THICKNESS = (
    PLATE_TOP_SPACER_THICKNESS + PLATE_TOP_SWITCH_THICKNESS + PLATE_TOP_COVER_THICKNESS
)
TOP_CUT_LOWER_THICKNESS = PLATE_TOP_SPACER_THICKNESS + PLATE_TOP_SWITCH_THICKNESS

skirt_height = PLATE_BOTTOM_THICKNESS + PCB_THICKNESS + 0.01
top_shell_height = skirt_height + TOP_CUT_TOTAL_THICKNESS


ORIGIN = cq.Vector(0, 0, 0)
SOLAR_WALL_THICKNESS = 3.9
SOLAR_TOP_THICKNESS = 1.13
SOLAR_CELL_THICKNESS = 2.1
SOLAR_TOP_Z = top_shell_height + SOLAR_WALL_THICKNESS
SOLAR_CEILING_TOP_Z = SOLAR_TOP_Z + SOLAR_TOP_THICKNESS

board_outline_sketch = (
    feature_sketch.get(BOARD_FEATURE_NAME).get("Edge.Cuts")
    .faces(cq.selectors.AreaNthSelector(-1))
)

feature_stages = {
    "plate_shells": {
        "placements": [(0, ORIGIN)],
        "stages": {
            "bottom_plate": {
                "sketch": board_outline_sketch,
                "operations": (
                    {
                        "target": "bottom_plate",
                        "kind": "union",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                    },
                ),
            },
            "top_shell": {
                "sketch": board_outline_sketch,
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "union",
                        "start": 0,
                        "end": top_shell_height,
                        "offset": SKIRT_THICKNESS,
                        "apply": lambda solid: solid.faces(">Z").fillet(TOP_FILLET_RADIUS),
                    },
                ),
            },
            "inner_clearance": {
                "sketch": board_outline_sketch,
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": 0,
                        "end": skirt_height,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "mounting_holes": {
        "placements": footprint_placements["mounting_holes"],
        "stages": {
            "drill": {
                "sketch": feature_sketch.get("mounting_holes").get("drill"),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        # we give the screw a little extra room so it doesn't bottom out and rip out
                        # the insert
                        "end": SCREW_LENGTH + TOLERANCE,
                        "offset": TOLERANCE,
                    },
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "battery_holder": {
        "placements": footprint_placements["battery_holder"],
        "stages": {
            "top": {
                "sketch": (
                    cq.Sketch()
                    .push([(2.47125, 0)])
                    .rect(16.3425, 45.505)
                    .reset()
                    .push([(7.64125, 0)])
                    .rect(6.0025, 40.4, mode="s")
                    .reset()
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": top_shell_height,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "bottom": {
                "sketch": cq.Sketch()
                .push([(-0.775, -0.025)])
                .rect(7.75, 44.14)
                .reset(),
                "operations": (
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "kailh_switches": {
        "placements": footprint_placements["kailh_switches"],
        "stages": {
            "lower": {
                "sketch": cq.Sketch().rect(14.5, 13.8),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "middle": {
                "batch_mode": "per-switch",
                "sketch": cq.Sketch().rect(13.8, 13.8).rect(3.0, 17.6),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                        "end": skirt_height + TOP_CUT_LOWER_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "upper": {
                "batch_mode": "per-switch",
                "sketch": (
                    cq.Sketch()
                    .rect(15.0, 15.0, tag="upper")
                    .select("upper")
                    .vertices()
                    .fillet(0.85)
                    .reset()
                    .rect(3.0, 17.6)
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height + TOP_CUT_LOWER_THICKNESS,
                        "end": top_shell_height,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "bottom": {
                # TODO (not for AI): move User.6 wires to "User.Drawings" or something like that
                "sketch": feature_sketch["kailh_switches"]["User.6"],
                "operations": (
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "inductors": {
        "placements": footprint_placements["inductors"],
        "stages": {
            "top": {
                "sketch": cq.Sketch().rect(4.6, 4.5),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": top_shell_height,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "capacitors": {
        "placements": footprint_placements["capacitors"],
        "stages": {
            "body": {
                "sketch": (
                    # TODO(not for AI): fix whatever caused copilot to bring in these origins -
                    # likely some quirk in how the capacitor footprint was drawn in KiCad
                    cq.Sketch().push([(0.001632, -0.003268)]).rect(2.8, 0.95).reset()
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                        "offset": TOLERANCE,
                    },
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "resistors": {
        "placements": footprint_placements["resistors"],
        "stages": {
            "body": {
                "sketch": cq.Sketch().rect(2.8, 0.95),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                        "offset": TOLERANCE,
                    },
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "power_ic": {
        "placements": footprint_placements["power_ic"],
        "stages": {
            "body": {
                "sketch": cq.Sketch().rect(3.8, 3.8),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                        "offset": TOLERANCE,
                    },
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "reset_button": {
        "placements": footprint_placements["reset_button"],
        "stages": {
            "top": {
                "sketch": (
                    cq.Sketch()
                    .push([(3.25, -2.25)])
                    .rect(7.5, 6.0, tag="button")
                    .select("button")
                    .vertices()
                    .fillet(0.5)
                    .reset()
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": top_shell_height,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "bottom": {
                "sketch": feature_sketch.get("reset_button", {}).get("pads"),
                "operations": (
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "solder_wires": {
        "placements": footprint_placements["solder_wires"],
        "stages": {
            "body": {
                "sketch": (
                    cq.Sketch()
                    .push([(0, -2.95)])
                    .rect(2.7, 8.6, tag="wire")
                    .select("wire")
                    .vertices()
                    .fillet(1.0)
                    .reset()
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": top_shell_height,
                        "offset": TOLERANCE,
                    },
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "microcontroller": {
        "placements": footprint_placements["microcontroller"],
        "stages": {
            "lower": {
                "sketch": (
                    cq.Workplane("XY")
                    .sketch()
                    .push([(-7.585002, 0.153997), (7.585002, 0.153997)])
                    .rect(2.539996, 17.780002, tag="controller_sockets")
                    .select("controller_sockets")
                    .reset()
                    .face(
                        # TODO(not for AI): see if we can somehow start with this as the base
                        # sketch, instead of placing it on top of the sockets
                        feature_sketch.get("microcontroller")
                        .get("F.CrtYd")
                        .wires("%CIRCLE")
                        .clean()
                    )
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": skirt_height + TOP_CUT_LOWER_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "upper": {
                "sketch": (
                    cq.Workplane("XY")
                    .center(0, 0.0905)
                    .sketch()
                    .rect(17.71, 20.955, tag="controller_body")
                    .select("controller_body")
                    .vertices()
                    .fillet(1.905)
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height + TOP_CUT_LOWER_THICKNESS,
                        "end": top_shell_height,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "bottom": {
                "sketch": (
                    cq.Workplane("XY")
                    .center(0, 0.0905)
                    .sketch()
                    .rect(17.71, 20.955)
                    .vertices()
                    .fillet(1.905)
                ),
                "operations": (
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    # TODO: this is missing despite being enabled
    "power_switch": {
        "placements": footprint_placements["power_switch"],
        "stages": {
            "top": {
                "sketch": (
                    cq.Sketch()
                    .rect(4.3, 14.8)
                    .arc((4.2, 4.75), (0, POWER_SWITCH_ARC_RADIUS), (-4.2, 4.75))
                    .segment((-4.2, -4.75), (-4.2, 4.75))
                    .arc((-4.2, -4.75), (0, -POWER_SWITCH_ARC_RADIUS), (4.2, -4.75))
                    .close()
                    .assemble()
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": skirt_height,
                        "end": top_shell_height,
                        "offset": TOLERANCE,
                    },
                ),
            },
            "bottom": {
                "sketch": feature_sketch.get("power_switch", {}).get("pads", cq.Sketch()),
                "operations": (
                    {
                        "target": "bottom_plate",
                        "kind": "cut",
                        "start": 0,
                        "end": PLATE_BOTTOM_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
    "solar_component": {
        "placements": [(0, ORIGIN)],
        "stages": {
            "wall_and_support": {
                "sketch": (
                    cq.Workplane("XY")
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
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "union",
                        "start": top_shell_height,
                        "end": SOLAR_TOP_Z,
                        "apply": lambda solid: solid.union(
                            cq.Workplane(
                                "XZ",
                                origin=(
                                    21.73 - 15.34 / 2 - TOLERANCE,
                                    -49.7 + 45.505 / 2 + TOLERANCE,
                                    top_shell_height,
                                ),
                            )
                            .lineTo(0, SOLAR_WALL_THICKNESS)
                            .lineTo(SOLAR_WALL_THICKNESS, SOLAR_WALL_THICKNESS)
                            .threePointArc(
                                (
                                    SOLAR_WALL_THICKNESS * (1 - 1 / sqrt(2)),
                                    SOLAR_WALL_THICKNESS / sqrt(2),
                                ),
                                (0, 0),
                            )
                            .close()
                            .extrude(45.505 + TOLERANCE)
                        ),
                    },
                ),
            },
            "top": {
                "sketch": (
                    cq.Workplane("XY")
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
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "union",
                        "start": SOLAR_TOP_Z,
                        "end": SOLAR_CEILING_TOP_Z,
                    },
                ),
            },
            "guard": {
                "sketch": (
                    cq.Workplane("XY")
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
                ),
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "union",
                        "start": SOLAR_CEILING_TOP_Z,
                        "end": SOLAR_CEILING_TOP_Z + SOLAR_CELL_THICKNESS,
                        "apply": lambda solid: solid.faces(">Z").fillet(
                            TOP_FILLET_RADIUS
                        ),
                    },
                ),
            },
            "cell_cut": {
                "placements": footprint_placements["solar_cell"],
                "sketch": feature_sketch["solar_cell"]["F.Fab"],
                "operations": (
                    {
                        "target": "top_plate_right",
                        "kind": "cut",
                        "start": SOLAR_CEILING_TOP_Z,
                        "end": SOLAR_CEILING_TOP_Z + SOLAR_CELL_THICKNESS,
                        "offset": TOLERANCE,
                    },
                ),
            },
        },
    },
}

model_solids = {
    "top_plate_right": None,
    "bottom_plate": None,
}
for feature in feature_stages.values():
    for stage in feature["stages"].values():
        placements = stage.get("placements", feature["placements"])
        if stage.get("batch_mode", "combined") == "per-switch":
            stage_batches = [
                {footprint_angle: [footprint_offset]}
                for footprint_angle, footprint_offset in placements
            ]
        else:
            placements_by_angle = defaultdict(list)
            for footprint_angle, footprint_offset in placements:
                placements_by_angle[footprint_angle].append(footprint_offset)
            stage_batches = [placements_by_angle]

        for placements_by_angle in stage_batches:
            profiles_by_offset = {}
            for operation in stage["operations"]:
                target = operation["target"]
                offset = operation.get("offset", 0)
                if offset not in profiles_by_offset:
                    placed_stage_sketch = cq.Workplane("XY").sketch()
                    has_faces = False
                    for footprint_angle, footprint_offsets in placements_by_angle.items():
                        placed_stage_sketch = (
                            placed_stage_sketch.push(footprint_offsets)
                            .face(stage["sketch"], angle=footprint_angle, mode="a")
                            .reset()
                        )
                        has_faces = True

                    if not has_faces:
                        profiles_by_offset[offset] = None
                    elif offset:
                        profiles_by_offset[offset] = (
                            placed_stage_sketch.faces()
                            .wires()
                            .offset(offset)
                            .clean()
                        )
                    else:
                        profiles_by_offset[offset] = placed_stage_sketch

                stage_profile = profiles_by_offset[offset]
                if stage_profile is None:
                    continue

                target_solid = model_solids[target]

                if operation["kind"] == "union":
                    new_workplane = cq.Workplane("XY")
                    if target_solid is None:
                        new_workplane = new_workplane.tag("base")
                    new_solid = (
                        new_workplane
                        .workplane(offset=operation["start"])
                        .placeSketch(stage_profile)
                        .extrude(operation["end"] - operation["start"])
                    )
                    if target_solid is None:
                        model_solids[target] = new_solid
                    else:
                        model_solids[target] = target_solid.union(new_solid)
                elif operation["kind"] == "cut":
                    if target_solid is None:
                        raise ValueError(f"{target} must exist before cut stages")
                    
                    model_solids[target] = (
                        target_solid
                        .workplaneFromTagged("base")
                        .workplane(offset=operation["start"])
                        .placeSketch(stage_profile)
                        .cutBlind(operation["end"] - operation["start"])
                    )

                else:
                    raise ValueError(f"Unsupported pipeline operation: {operation['kind']}")
                
                apply = operation.get("apply")
                if apply is not None:
                    model_solids[target] = apply(model_solids[target])

top_plate_right = model_solids["top_plate_right"]
bottom_plate = model_solids["bottom_plate"]

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
    for footprint_angle, footprint_offset in footprint_placements["mounting_holes"]
    for face in feature_sketch["mounting_holes"]["drill"]
    .moved(cq.Location(footprint_offset, cq.Vector(0, 0, 1), footprint_angle))
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
    pcb_assembly,
    top_plate_right,
    *hardware_instances,
]
preview_colors = [
    "#707070",
    "#ffc731",
    "#5994dc",
    "#ff0000",
    "#00ff00",
]

if args.preview:
    show(*preview_objects, colors=preview_colors)
