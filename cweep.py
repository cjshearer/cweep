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
import os
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


def finalize_raw_sketch(sketch):
    finalized = cq.Sketch()
    for face in sketch.faces().vals():
        finalized = finalized.face(face, mode="a")
    for wire in edgesToWires(sketch._edges):
        if not wire.wrapped.Closed():
            continue
        finalized = finalized.face(wire, mode="a")
    return finalized


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

feature_sketch[BOARD_FEATURE_NAME] = {
    layer_name: finalize_raw_sketch(layer_sketch)
    for layer_name, layer_sketch in dict(feature_sketch[BOARD_FEATURE_NAME]).items()
}

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

    feature_sketch[feature_name] = dict(feature_sketch[feature_name])
    for layer_name, layer_sketch in feature_sketch[feature_name].items():
        if not layer_sketch._edges:
            continue
        feature_sketch[feature_name][layer_name] = finalize_raw_sketch(layer_sketch)


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
    PLATE_TOP_SPACER_THICKNESS + PLATE_TOP_SWITCH_THICKNESS + PLATE_TOP_COVER_THICKNESS
)
TOP_CUT_LOWER_THICKNESS = PLATE_TOP_SPACER_THICKNESS + PLATE_TOP_SWITCH_THICKNESS

skirt_height = PLATE_BOTTOM_THICKNESS + PCB_THICKNESS + 0.01
top_shell_height = skirt_height + TOP_CUT_TOTAL_THICKNESS

# TODO: I think we can improve the speed of this script by going back to using sketches as
# intermediate objects, where sketches are assembled for each layer and a single cut operation is
# performed per layer, rather than constructing many objects and performing 3d boolean operations
# between them and the main case bodies. Let's try adapting our approach to do this. The overall
# pipeline should look something like:
#
# this needs a nice way to associate each sketch with the height to which it should be extruded. We
# will later combine all features that begin extrusions at the same height, or those that fall
# within the cut range, so that we can minimize the number of cut operations we need to perform on
# the main case bodies. Pick some nice data structure that represents this association and makes it
# easy to combine the sketches for each layer, given the operations we will need to do to find which
# sketch is "active" at a given height.
#
# feature_sketch.example_feature = {
#     bottom_or_same_recognizable_name_for_this_sketch_that_should_be_ordered_from_bottom_to_top = {
#         sketch = (
#             cq.Sketch()
#             .create_some_shapes_to_be_used_in_a_layer_height_range()
#             ....,
#             # don't apply tolerance offset here. We'll apply it layer for combined sketches
#         ),
#         # ranges to be applied to this sketch for the top plate
#         top_plate = {
#             start = 0, # the height at which the cut should start for these shapes
#             end = 5, # the height at which the cut should end for these shapes,
#         }
#         # whether this sketch is used to cut out the bottom plate, which has only one layer
#         bottom_plate = True
#     }
#
#     ....
#
#     other_feature = {
#         ...
#     }
# }
#
# features.other_feature = ...the rest of the feature sketches
#
# then we combine the sketches into spans that the cuts should be applied along, where if two spans
# overlap, say we make a rect from 0 to 5 and a circle from 2 to 7, we would get 0-2 rect, 2-5 rect
# +circle, 5-7 circle.
#
# bottom_plate_combined_sketches = cq.Sketch()
# for start, end, active_sketches in sketch_spans:
#     top_plate_combined_sketches = cq.Sketch()
#     for active_sketch in active_sketches:
#         top_plate_combined_sketches = top_plate_combined_sketches.face(active_sketch)
#         if active_sketch.bottom_plate:
#             bottom_plate_combined_sketches = bottom_plate_combined_sketches.face(active_sketch)
#     top_plate_combined_sketches = top_plate_combined_sketches.wires().offset(TOLERANCE).finalize()
#     top_plate = (
#       top_plate.faces(">Z")
#       .workplane(offset=start)
#       .center(0, 0)
#       .placeSketch(top_plate_combined_sketches)
#       .cutBlind(end - start)
#     )
#
# bottom_plate_combined_sketches = bottom_plate_combined_sketches.wires().offset(TOLERANCE).finalize()
# bottom_plate = (
#     bottom_plate.faces(">Z")
#     .workplane(offset=0)
#     .center(0, 0)
#     .placeSketch(bottom_plate_combined_sketches)
#     .cutBlind(PLATE_BOTTOM_THICKNESS)
# )
#
# Be sure to save the current volume of the plates as a reference. They should be largely the same,
# although moving the tolerances to be applied globally will result in some slight differences,
# since we are not currently applying those everywhere the way that we should be.


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
            .face(
                feature_sketch["solar_cell"]["F.Fab"].moved(
                    cq.Location(
                        footprint_placements["solar_cell"][0][1],
                        cq.Vector(0, 0, 1),
                        footprint_placements["solar_cell"][0][0],
                    )
                ),
                mode="a",
            )
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


mounting_hole_sketch = feature_sketch.get("mounting_holes", {}).get(
    "drill", cq.Sketch()
)
reset_button_bottom_sketch = feature_sketch.get("reset_button", {}).get(
    "pads", cq.Sketch()
)
power_switch_bottom_sketch = feature_sketch.get("power_switch", {}).get(
    "pads", cq.Sketch()
)

power_switch_top_sketch = cq.Sketch().rect(8.4, 9.5).rect(4.3, 14.8, mode="a")
for y_sign in [1, -1]:
    power_switch_arc = (
        cq.Workplane("XY")
        .moveTo(-4.2, y_sign * 4.75)
        .lineTo(4.2, y_sign * 4.75)
        .threePointArc((0, y_sign * POWER_SWITCH_ARC_RADIUS), (-4.2, y_sign * 4.75))
        .close()
        .val()
    )
    power_switch_top_sketch = power_switch_top_sketch.face(power_switch_arc, mode="a")

kailh_bottom_sketch = cq.Sketch()
kailh_front_socket_faces = (
    feature_sketch.get("kailh_switches", {}).get("F.Fab", cq.Sketch()).faces().vals()
)
kailh_back_socket_faces = (
    feature_sketch.get("kailh_switches", {}).get("B.Fab", cq.Sketch()).faces().vals()
)
kailh_drill_faces = (
    feature_sketch.get("kailh_switches", {}).get("drill", cq.Sketch()).faces().vals()
)
if kailh_front_socket_faces and kailh_back_socket_faces and kailh_drill_faces:
    kailh_front_socket_face = min(
        kailh_front_socket_faces, key=lambda face: face.Area()
    )
    kailh_back_socket_face = kailh_back_socket_faces[0]

    drill_points_by_radius = defaultdict(list)
    for drill_face in kailh_drill_faces:
        drill_bounding_box = drill_face.BoundingBox()
        drill_radius = round((drill_bounding_box.xmax - drill_bounding_box.xmin) / 2, 6)
        drill_points_by_radius[drill_radius].append(
            (drill_face.Center().x, drill_face.Center().y)
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

    top_y = max(drill_face.Center().y for drill_face in kailh_drill_faces)
    top_drill_faces = sorted(
        [
            drill_face
            for drill_face in kailh_drill_faces
            if abs(drill_face.Center().y - top_y) < 1e-6
        ],
        key=lambda drill_face: drill_face.Center().x,
    )
    bridge_specs = []
    for top_drill_face in [top_drill_faces[0], top_drill_faces[-1]]:
        top_drill_bounding_box = top_drill_face.BoundingBox()
        socket_face = min(
            [kailh_back_socket_face, kailh_front_socket_face],
            key=lambda face: abs(face.Center().x - top_drill_face.Center().x),
        )
        socket_top_y = socket_face.BoundingBox().ymax
        bridge_specs.append(
            (
                (
                    top_drill_face.Center().x,
                    (top_drill_face.Center().y + socket_top_y) / 2,
                ),
                top_drill_bounding_box.xmax - top_drill_bounding_box.xmin,
                top_drill_face.Center().y - socket_top_y,
            )
        )

    kailh_bottom_sketch = (
        cq.Sketch()
        .face(kailh_back_socket_face, mode="a")
        .face(kailh_front_socket_face, mode="a")
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
        .reset()
    )

all_feature_cut_sketches = {
    "board_cutout": {
        "placements": [(0, cq.Vector(0, 0, 0))],
        "stages": {
            "body": {
                "sketch": (
                    cq.Workplane("XY")
                    .center(27.40125, -49.7)
                    .sketch()
                    .rect(6.0025, 40.4)
                ),
                "top_plate": {
                    "start": skirt_height,
                    "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                },
            },
            "tabs": {
                "sketch": (
                    cq.Workplane("XY")
                    .center(27.40125, -49.7)
                    .sketch()
                    .push([(0, 19.10125), (0, -19.10125)])
                    .rect(6.0025, 2.1975)
                ),
                "top_plate": {
                    "start": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                    "end": top_shell_height,
                },
            },
        },
    },
    "mounting_holes": {
        "placements": footprint_placements["mounting_holes"],
        "stages": {
            "drill": {
                "sketch": mounting_hole_sketch,
                "top_plate": {
                    "start": skirt_height,
                    "end": skirt_height + TOP_CUT_LOWER_THICKNESS,
                },
                "bottom_plate": True,
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
                "top_plate": {
                    "start": skirt_height,
                    "end": top_shell_height,
                },
            },
            "bottom": {
                "sketch": cq.Sketch()
                .push([(-0.775, -0.025)])
                .rect(7.75, 44.14)
                .reset(),
                "bottom_plate": True,
            },
        },
    },
    "kailh_switches": {
        "placements": footprint_placements["kailh_switches"],
        "stages": {
            "lower": {
                "sketch": cq.Sketch().rect(14.5, 13.8),
                "top_plate": {
                    "start": skirt_height,
                    "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                },
            },
            "middle": {
                "sketch": cq.Sketch().rect(13.8, 13.8).rect(3.0, 17.6, mode="a"),
                "top_plate": {
                    "start": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                    "end": skirt_height + TOP_CUT_LOWER_THICKNESS,
                },
            },
            "upper": {
                "sketch": (
                    cq.Sketch()
                    .rect(15.0, 15.0, tag="upper")
                    .select("upper")
                    .vertices()
                    .fillet(0.85)
                    .reset()
                    .rect(3.0, 17.6, mode="a")
                ),
                "top_plate": {
                    "start": skirt_height + TOP_CUT_LOWER_THICKNESS,
                    "end": top_shell_height,
                },
            },
            "bottom": {
                "sketch": kailh_bottom_sketch,
                "bottom_plate": True,
            },
        },
    },
    "inductors": {
        "placements": footprint_placements["inductors"],
        "stages": {
            "top": {
                "sketch": cq.Sketch().rect(4.6, 4.5),
                "top_plate": {
                    "start": skirt_height,
                    "end": top_shell_height,
                },
            },
        },
    },
    "capacitors": {
        "placements": footprint_placements["capacitors"],
        "stages": {
            "body": {
                "sketch": (
                    cq.Sketch().push([(0.001632, -0.003268)]).rect(2.8, 0.95).reset()
                ),
                "top_plate": {
                    "start": skirt_height,
                    "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                },
                "bottom_plate": True,
            },
        },
    },
    "resistors": {
        "placements": footprint_placements["resistors"],
        "stages": {
            "body": {
                "sketch": cq.Sketch().rect(2.8, 0.95),
                "top_plate": {
                    "start": skirt_height,
                    "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                },
                "bottom_plate": True,
            },
        },
    },
    "power_ic": {
        "placements": footprint_placements["power_ic"],
        "stages": {
            "body": {
                "sketch": cq.Sketch().rect(3.8, 3.8),
                "top_plate": {
                    "start": skirt_height,
                    "end": skirt_height + PLATE_TOP_SPACER_THICKNESS,
                },
                "bottom_plate": True,
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
                "top_plate": {
                    "start": skirt_height,
                    "end": top_shell_height,
                },
            },
            "bottom": {
                "sketch": reset_button_bottom_sketch,
                "bottom_plate": True,
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
                "top_plate": {
                    "start": skirt_height,
                    "end": top_shell_height,
                },
                "bottom_plate": True,
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
                        feature_sketch.get("microcontroller")
                        .get("F.CrtYd")
                        .edges("%CIRCLE")
                    )
                ),
                "top_plate": {
                    "start": skirt_height,
                    "end": skirt_height + TOP_CUT_LOWER_THICKNESS,
                },
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
                "top_plate": {
                    "start": skirt_height + TOP_CUT_LOWER_THICKNESS,
                    "end": top_shell_height,
                },
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
                "bottom_plate": True,
            },
        },
    },
    "power_switch": {
        "placements": footprint_placements["power_switch"],
        "stages": {
            "top": {
                "sketch": power_switch_top_sketch,
                "top_plate": {
                    "start": skirt_height,
                    "end": top_shell_height,
                },
            },
            "bottom": {
                "sketch": power_switch_bottom_sketch,
                "bottom_plate": True,
            },
        },
    },
}

# Keep restore work incremental until each added feature is measured.
RESTORED_FEATURE_BATCHES = (
    ("battery_holder",),
    ("power_ic",),
    ("reset_button",),
    ("power_switch",),
    ("solder_wires",),
    ("inductors",),
    ("capacitors",),
    ("resistors",),
)
RESTORE_BATCH_COUNT = int(os.environ.get("CWEEP_RESTORE_BATCH_COUNT", "0"))
if not 0 <= RESTORE_BATCH_COUNT <= len(RESTORED_FEATURE_BATCHES):
    raise ValueError(
        "CWEEP_RESTORE_BATCH_COUNT must be between 0 and "
        f"{len(RESTORED_FEATURE_BATCHES)}"
    )
ENABLED_RESTORED_FEATURES = [
    feature_name
    for batch in RESTORED_FEATURE_BATCHES[:RESTORE_BATCH_COUNT]
    for feature_name in batch
]
BASE_FEATURE_NAMES = ("board_cutout", "mounting_holes", "microcontroller")
feature_cut_sketches = {
    feature_name: all_feature_cut_sketches[feature_name]
    for feature_name in (*BASE_FEATURE_NAMES, *ENABLED_RESTORED_FEATURES)
}

board_outline_sketch = cq.Sketch().face(
    feature_sketch.get(BOARD_FEATURE_NAME, {})
    .get("Edge.Cuts")
    .wires(cq.selectors.LengthNthSelector(-1))
)

top_plate_right = (
    cq.Workplane("XY")
    .placeSketch(board_outline_sketch)
    .extrude(PLATE_BOTTOM_THICKNESS)
    .faces("<Z")
    .wires()
    .toPending()
    .offset2D(SKIRT_THICKNESS)
    .extrude(top_shell_height)
    .faces(">Z")
    .fillet(TOP_FILLET_RADIUS)
    # TODO: move this to be a feature like the others, so that it can take advantage of the same cut
    # pipeline we already have
    .cut(
        cq.Workplane("XY")
        .placeSketch(board_outline_sketch)
        .extrude(PLATE_BOTTOM_THICKNESS)
        .faces("<Z")
        .wires()
        .toPending()
        .offset2D(TOLERANCE)
        .extrude(skirt_height)
    )
    .union(build_top_solar_component())
)

bottom_plate = (
    cq.Workplane("XY").placeSketch(board_outline_sketch).extrude(PLATE_BOTTOM_THICKNESS)
)

bottom_cutout_sketch = cq.Workplane("XY").sketch()
bottom_has_faces = False
for feature in feature_cut_sketches.values():
    placements_by_angle = defaultdict(list)
    for footprint_angle, footprint_offset in feature["placements"]:
        placements_by_angle[footprint_angle].append(footprint_offset)

    for stage in feature["stages"].values():
        top_plate = stage.get("top_plate")
        bottom_plate_enabled = stage.get("bottom_plate")
        if top_plate is None and not bottom_plate_enabled:
            continue

        top_stage_sketch = cq.Workplane("XY").sketch()
        top_has_faces = False
        bottom_stage_has_faces = False
        for footprint_angle, footprint_offsets in placements_by_angle.items():
            if top_plate is not None:
                top_stage_sketch = (
                    top_stage_sketch.push(footprint_offsets)
                    .face(stage["sketch"], angle=footprint_angle, mode="a")
                    .reset()
                )
                top_has_faces = True

            if bottom_plate_enabled:
                bottom_cutout_sketch = (
                    bottom_cutout_sketch.push(footprint_offsets)
                    .face(stage["sketch"], angle=footprint_angle, mode="a")
                    .reset()
                )
                bottom_stage_has_faces = True

        if top_has_faces:
            top_plate_right = top_plate_right.cut(
                cq.Workplane("XY")
                .workplane(offset=top_plate["start"])
                .placeSketch(
                    top_stage_sketch.faces().wires().offset(TOLERANCE).finalize().val()
                )
                .extrude(top_plate["end"] - top_plate["start"])
            )

        bottom_has_faces = bottom_has_faces or bottom_stage_has_faces

if bottom_has_faces:
    bottom_plate = bottom_plate.cut(
        cq.Workplane("XY")
        .placeSketch(
            bottom_cutout_sketch.faces().wires().offset(TOLERANCE).finalize().val()
        )
        .extrude(PLATE_BOTTOM_THICKNESS)
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
