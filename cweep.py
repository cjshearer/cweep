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


def wires_from_edges(edges):
    # Flipping KiCad's Y axis reflects loop winding, so normalize planar wires before sketching.
    normalized = []
    for wire in edgesToWires(edges):
        if not wire.wrapped.Closed():
            normalized.append(wire)
            continue

        if cq.Face.makeFromWires(wire).normalAt().z < 0:
            wire = cq.Shape.cast(wire.wrapped.Reversed())
        normalized.append(wire)
    return normalized


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

for item in raw_board.graphicItems:
    feature_edges[BOARD_FEATURE_NAME][item.layer].extend(item_to_edges(item))

for footprint in footprints:
    feature_name = FEATURE_NAME_BY_LIB_ID[footprint.libId]
    footprint_angle = footprint.position.angle or 0
    footprint_offset = kicad_xy(footprint.position.X, footprint.position.Y)
    footprint_edges = defaultdict(list)

    for item in getattr(footprint, "graphicItems", []):
        footprint_edges[item.layer].extend(item_to_edges(item))

    # We handle drill holes as circular wires based on their diameter. Currently, non-circular
    # drills are unsupported.
    for pad in getattr(footprint, "pads", []):
        pad_position = getattr(pad, "position", None) or getattr(pad, "at", None)
        drill = getattr(pad, "drill", None)
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

BOTTOM_CUTOUT_FEATURES = [
    feature_wire.get("battery_holder").get("User.6"),
    feature_wire.get("capacitors").get("User.6"),
    feature_wire.get("kailh_switches").get("User.6"),
    feature_wire.get("microcontroller").get("User.6"),
    feature_wire.get("power_ic").get("User.6"),
    feature_wire.get("power_switch").get("User.6"),
    feature_wire.get("reset_button").get("User.6"),
    feature_wire.get("resistors").get("User.6"),
    feature_wire.get("solder_wires").get("User.6"),
]

TOP_CUT_OPERATIONS = [
    {
        "thickness": PLATE_TOP_SPACER_THICKNESS,
        "features": [
            feature_wire.get("battery_holder").get("User.5"),
            feature_wire.get(BOARD_FEATURE_NAME).get("User.5"),
            feature_wire.get("kailh_switches").get("User.5"),
            feature_wire.get("microcontroller").get("User.5"),
            feature_wire.get("power_switch").get("User.5"),
            feature_wire.get("reset_button").get("User.5"),
            feature_wire.get("resistors").get("User.5"),
            feature_wire.get("solder_wires").get("User.5"),
        ],
    },
    {
        "thickness": PLATE_TOP_SWITCH_THICKNESS,
        "features": [
            feature_wire.get("battery_holder").get("User.4"),
            feature_wire.get(BOARD_FEATURE_NAME).get("User.4"),
            feature_wire.get("inductors").get("User.4"),
            feature_wire.get("kailh_switches").get("User.4"),
            feature_wire.get("microcontroller").get("User.4"),
            feature_wire.get("power_switch").get("User.4"),
            feature_wire.get("reset_button").get("User.4"),
            feature_wire.get("solder_wires").get("User.4"),
        ],
    },
    {
        "thickness": PLATE_TOP_COVER_THICKNESS,
        "features": [
            feature_wire.get("battery_holder").get("User.3"),
            feature_wire.get(BOARD_FEATURE_NAME).get("User.3"),
            feature_wire.get("inductors").get("User.3"),
            feature_wire.get("kailh_switches").get("User.3"),
            feature_wire.get("microcontroller").get("User.3"),
            feature_wire.get("power_switch").get("User.3"),
            feature_wire.get("reset_button").get("User.3"),
            feature_wire.get("solder_wires").get("User.3"),
        ],
    },
]

TOP_FILL_OPERATIONS = [
    {
        "thickness": PLATE_TOP_SOLAR_WALL_THICKNESS,
        "features": [feature_wire.get(BOARD_FEATURE_NAME).get("User.2")],
    },
    {
        "thickness": PLATE_TOP_SOLAR_TOP_THICKNESS,
        "features": [feature_wire.get(BOARD_FEATURE_NAME).get("User.1")],
    },
]


skirt_height = PLATE_BOTTOM_THICKNESS + PCB_THICKNESS + 0.01
top_shell_height = skirt_height + sum(op["thickness"] for op in TOP_CUT_OPERATIONS)
solar_ceiling_top_z = top_shell_height + sum(
    op["thickness"] for op in TOP_FILL_OPERATIONS
)

board_outline_wires = feature_wire.get(BOARD_FEATURE_NAME).get("User.7", [])
mounting_hole_wires = offset_wires(
    feature_wire.get("mounting_holes").get("drill", []),
    TOLERANCE,
)
footprint_cutout_wires = offset_wires(
    [wire for wire_group in BOTTOM_CUTOUT_FEATURES for wire in wire_group],
    TOLERANCE,
)
solar_cell_cutout_wires = offset_wires(
    feature_wire.get("solar_cell").get("F.Fab", []),
    TOLERANCE,
)
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

current_z = top_shell_height
for op in TOP_FILL_OPERATIONS:
    layer_offset_wires = offset_wires(
        [wire for wire_group in op["features"] for wire in wire_group],
        -TOLERANCE,
    )
    top_plate = top_plate.union(
        profile_from_wires(layer_offset_wires, offset=current_z).extrude(
            op["thickness"]
        )
    )
    current_z += op["thickness"]

current_z = skirt_height
for op in TOP_CUT_OPERATIONS:
    cut_wires = (
        offset_wires(
            [wire for wire_group in op["features"] for wire in wire_group],
            TOLERANCE,
        )
        + mounting_hole_wires
    )
    top_plate = top_plate.cut(
        profile_from_wires(cut_wires, offset=current_z).extrude(op["thickness"])
    )
    current_z += op["thickness"]

# We protect the edges of the solar cell by adding a thin wall that the cell will sit flush within
solar_wall_wires = offset_wires(
    feature_wire.get(BOARD_FEATURE_NAME).get("User.2", []),
    -TOLERANCE,
)

solar_top_wires = offset_wires(
    feature_wire.get(BOARD_FEATURE_NAME).get("User.1", []),
    -TOLERANCE,
)

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
    wire.Center() for wire in mounting_hole_wires
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
