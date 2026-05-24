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
    feature_name = FEATURE_NAME_BY_LIB_ID[footprint.libId]
    footprint_angle = footprint.position.angle or 0
    footprint_offset = kicad_xy(footprint.position.X, footprint.position.Y)
    footprint_placements[feature_name].append((footprint_angle, footprint_offset))
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

# TODO: after finishing the other tasks, my hope is that this helper is gone.
def local_workplane_wires(build_local_wires):
    return normalize_wires(build_local_wires(cq.Workplane("XY")).vals())


def merged_wires(wires):
    merged = cq.Sketch()
    for wire in wires:
        merged.face(wire, mode="a")
    merged.clean()
    return [wire for face in merged._faces.Faces() for wire in face.Wires()]

# TODO: after finishing the other tasks, my hope is that this helper is gone.
def sketch_wires(sketch, offset=(0, 0, 0)):
    # Sketch primitives let us express most footprint cutouts as simple booleans.
    raw_wires = [
        wire.translate(offset)
        for face in sketch._faces.Faces()
        for wire in face.Wires()
    ]
    return merged_wires(raw_wires)


# TODO: inline this into its single call site
def largest_closed_wire(wires):
    closed_wires = [wire for wire in wires if wire.wrapped.Closed()]
    if not closed_wires:
        return None
    return max(closed_wires, key=lambda wire: cq.Face.makeFromWires(wire).Area())

# TODO: after finishing the other tasks, my hope is that this helper is gone.
def local_sketch_wires(build_local_sketch, offset=(0, 0, 0)):
    return sketch_wires(build_local_sketch(), offset)


# Build 3D plates based on extracted edges and specified dimensions --------------------------------

# TODO: after other tasks, inline this into what should be the remaining two call sites.
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


# TODO: after finishing the other tasks, my hope is that this helper is gone.
def solid_from_wires(wires, thickness, offset=0, xy_offset=0):
    # Keep the current XY-only tolerance behavior; future 3D growth can happen here.
    if xy_offset == 0:
        return profile_from_wires(wires, offset=offset).extrude(thickness)
    return profile_from_wires(offset_wires(wires, xy_offset), offset=offset).extrude(
        thickness
    )


def solid_from_faces(faces, thickness, offset=0):
    add_wires = []
    sub_wires = []
    for face in faces:
        add_wires.append(face.outerWire())
        sub_wires.extend(face.innerWires())
    return profile_from_wires(add_wires, sub_wires, offset=offset).extrude(thickness)


def staged_solid(stages, xy_offset=0):
    solid = None
    for wires, offset, thickness in stages:
        stage_solid = solid_from_wires(
            wires,
            thickness,
            offset=offset,
            xy_offset=xy_offset,
        )
        solid = stage_solid if solid is None else solid.union(stage_solid, clean=False)
    return solid


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

# TODO: inline this into a single fluent api call and inline this function into its one call site
def power_switch_top_sketch():
    sketch = cq.Sketch().rect(8.4, 9.5).rect(4.3, 14.8, mode="a")
    for y_sign in [1, -1]:
        arc = (
            cq.Workplane("XY")
            .moveTo(-4.2, y_sign * 4.75)
            .lineTo(4.2, y_sign * 4.75)
            .threePointArc((0, y_sign * POWER_SWITCH_ARC_RADIUS), (-4.2, y_sign * 4.75))
            .close()
            .val()
        )
        sketch.face(arc, mode="a")
    return sketch


def build_kailh_cutout():
    return staged_solid(
        [
            (
                local_workplane_wires(lambda wp: wp.rect(14.5, 13.8)),
                skirt_height,
                PLATE_TOP_SPACER_THICKNESS,
            ),
            (
                local_sketch_wires(
                    lambda: cq.Sketch().rect(13.8, 13.8).rect(3.0, 17.6, mode="a")
                ),
                skirt_height + PLATE_TOP_SPACER_THICKNESS,
                PLATE_TOP_SWITCH_THICKNESS,
            ),
            (
                local_sketch_wires(
                    lambda: (
                        cq.Sketch()
                        .rect(15.0, 15.0)
                        .vertices()
                        .fillet(0.85)
                        .reset()
                        .rect(3.0, 17.6, mode="a")
                    )
                ),
                skirt_height + TOP_CUT_LOWER_THICKNESS,
                PLATE_TOP_COVER_THICKNESS,
            ),
        ],
        xy_offset=TOLERANCE,
    )


# TODO: build this as a single fluent API call, where each stage is added as a profile on top of the
# previous one. The result of this function call should be a 3D solid. There is no reason to use any
# shared helpers for this.
def build_battery_holder_cutout():
    return solid_from_wires(
        local_sketch_wires(
            lambda: (
                cq.Sketch()
                .rect(16.3425, 45.505)
                .push([(5.17, 0)])
                .rect(6.0025, 40.4, mode="s")
            ),
            offset=(2.47125, 0, 0),
        ),
        TOP_CUT_TOTAL_THICKNESS,
        offset=skirt_height,
        xy_offset=TOLERANCE,
    )


def build_inductor_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(4.6 + 2 * TOLERANCE, 4.5 + 2 * TOLERANCE, tag="inductor")
        .select("inductor")
        .vertices()
        .fillet(TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )


def build_capacitor_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(0.001632, -0.003268)
        .sketch()
        .rect(2.8 + 2 * TOLERANCE, 0.95 + 2 * TOLERANCE, tag="capacitor")
        .select("capacitor")
        .vertices()
        .fillet(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
    )


def build_resistor_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(2.8 + 2 * TOLERANCE, 0.95 + 2 * TOLERANCE, tag="resistor")
        .select("resistor")
        .vertices()
        .fillet(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
    )


def build_power_ic_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .rect(3.8 + 2 * TOLERANCE, 3.8 + 2 * TOLERANCE, tag="power_ic")
        .select("power_ic")
        .vertices()
        .fillet(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
    )


def build_reset_button_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(3.25, -2.25)
        .sketch()
        .rect(7.5 + 2 * TOLERANCE, 6.0 + 2 * TOLERANCE, tag="reset_button")
        .select("reset_button")
        .vertices()
        .fillet(0.5 + TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )


def build_solder_wire_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(0, -2.95)
        .sketch()
        .rect(2.7 + 2 * TOLERANCE, 8.6 + 2 * TOLERANCE, tag="solder_wire")
        .select("solder_wire")
        .vertices()
        .fillet(1.0 + TOLERANCE)
        .finalize()
        .extrude(TOP_CUT_TOTAL_THICKNESS)
    )

def build_microcontroller_cutout():
    lower_stage = (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .sketch()
        .push([(-7.585002, 0.153997), (7.585002, 0.153997)])
        .rect(
            2.539996 + 2 * TOLERANCE,
            17.780002 + 2 * TOLERANCE,
            tag="side_rails",
        )
        .select("side_rails")
        .vertices()
        .fillet(TOLERANCE)
        .reset()
    )
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
    return (
        lower_stage.finalize()
        .extrude(TOP_CUT_LOWER_THICKNESS)
        .faces(">Z")
        .workplane()
        .center(0, 0.0905)
        .sketch()
        .rect(17.71 + 2 * TOLERANCE, 20.955 + 2 * TOLERANCE, tag="upper")
        .select("upper")
        .vertices()
        .fillet(1.905 + TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_COVER_THICKNESS)
    )


# TODO: build this as a single fluent API call, where each stage is added as a profile on top of the
# previous one. The result of this function call should be a 3D solid. There is no reason to use any
# shared helpers for this.
def build_power_switch_cutout():
    return solid_from_wires(
        local_sketch_wires(power_switch_top_sketch),
        TOP_CUT_TOTAL_THICKNESS,
        offset=skirt_height,
        xy_offset=TOLERANCE,
    )


def build_board_cutout():
    return (
        cq.Workplane("XY")
        .workplane(offset=skirt_height)
        .center(27.40125, -49.7)
        .sketch()
        .rect(6.0025 + 2 * TOLERANCE, 40.4 + 2 * TOLERANCE, tag="body")
        .select("body")
        .vertices()
        .fillet(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SPACER_THICKNESS)
        .faces(">Z")
        .workplane()
        .sketch()
        .push([(0, 19.10125), (0, -19.10125)])
        .rect(6.0025 + 2 * TOLERANCE, 2.1975 + 2 * TOLERANCE, tag="tabs")
        .select("tabs")
        .vertices()
        .fillet(TOLERANCE)
        .finalize()
        .extrude(PLATE_TOP_SWITCH_THICKNESS + PLATE_TOP_COVER_THICKNESS)
    )


# TODO: inline this into its single call site
def build_bottom_cutout_from_top(build_top_local_solid):
    lowered_solid = build_top_local_solid().translate((0, 0, -skirt_height))
    return solid_from_faces(
        cq.Workplane().add(lowered_solid.val()).faces("<Z").vals(),
        PLATE_BOTTOM_THICKNESS,
    )


# TODO: construct this from a single fluent API call. Start with a sketch, on which you place the
# drill wires. Then, select the circles furthest in the +Y direction, and among the top three,
# select the pair furthest in the +X and -X direction. For each of those two wires, construct a
# rectangle that extends down to the top of the socket wire, and union all those rectangles together
# with the drill wires. Then union that result with the front socket wire and the back socket wire.
# This should be achievable in one long API call. Then, inline this function into its one call site,
# which should again result in a single fluent API call that constructs the bottom cutout solid
# directly without any intermediate wires or sketches. The result of this should be different,
# specifically it should have a slightly smaller volume, as currently the rectangle in the negative
# X direction does not quite extend all the way down to the socket. That said, the current approach
# appears to create a rectangle for each drill, including the one in the center. The drill in the
# center (it has the same, or nearly the same Y value as the top two drills), should not have any
# rectangle joining it to the sockets below. If you need references to ensure that you have
# constructed this correctly, look at the deprecated User.6 kailh_switches layer.
def build_kailh_bottom_socket_local_wires():
    front_fab_wires = feature_local_wire.get("kailh_switches", {}).get("F.Fab", [])
    back_fab_wires = feature_local_wire.get("kailh_switches", {}).get("B.Fab", [])
    drill_wires = feature_local_wire.get("kailh_switches", {}).get("drill", [])

    front_socket_wire = min(
        front_fab_wires,
        key=lambda wire: cq.Face.makeFromWires(wire).Area(),
    )
    top_y = max(wire.Center().y for wire in drill_wires)
    top_drill_wires = [wire for wire in drill_wires if abs(wire.Center().y - top_y) < 1e-6]
    socket_wires = [*back_fab_wires, front_socket_wire]
    join_wires = []

    for top_drill_wire in top_drill_wires:
        top_drill_bb = top_drill_wire.BoundingBox()
        socket_wire = min(
            socket_wires,
            key=lambda wire: abs(wire.Center().x - top_drill_wire.Center().x),
        )
        socket_top_y = socket_wire.BoundingBox().ymax
        join_center_x = top_drill_wire.Center().x
        join_center_y = (top_drill_wire.Center().y + socket_top_y) / 2
        join_width = top_drill_bb.xmax - top_drill_bb.xmin
        join_height = top_drill_wire.Center().y - socket_top_y
        join_wires.extend(
            local_workplane_wires(
                lambda wp: wp.center(join_center_x, join_center_y).rect(
                    join_width,
                    join_height,
                )
            )
        )

    return merged_wires(socket_wires + drill_wires + join_wires)


def build_kailh_bottom_cutout():
    return solid_from_wires(
        build_kailh_bottom_socket_local_wires(),
        PLATE_BOTTOM_THICKNESS
    )

# TODO: as much as possible, build this as a single fluent API call that results in a 3D solid. This
# should not need any shared helpers. I do want to retain my comments within, so that it is still
# clear what is doing what.
def build_top_solar_component():
    solar_wall_thickness = 3.9
    solar_top_thickness = 1.13
    solar_cell_thickness = 2.1
    solar_top_z = top_shell_height + solar_wall_thickness
    solar_ceiling_top_z = solar_top_z + solar_top_thickness

    def build_solar_base_sketch():
        return (
            cq.Sketch()
            .push([(20.5375, -48.7)])
            .rect(17.725, 47.505, tag="solar_outer")
            .select("solar_outer")
            .vertices("<X and >Y")
            .fillet(2.0)
            .reset()
        )

    def build_solar_wall_sketch():
        return (
            build_solar_base_sketch()
            .push([(21.73, -49.7)])
            .rect(15.34, 45.505, mode="s", tag="battery_holder_cutout")
            .reset()
            .push([(26.9, -49.7)])
            .rect(5.0, 36.005, mode="a", tag="battery_holder_wall")
        )

    def build_solar_top_sketch():
        return (
            build_solar_base_sketch()
            .push([(21.18, -49.92125)])
            .rect(6.44, 45.0625, mode="s", tag="solar_cell_recess")
            .reset()
            .push([(26.9, -70.0775)])
            .rect(5.0, 4.75, mode="s", tag="battery_clearance")
        )

    def solid_from_sketch(sketch, thickness, offset, xy_offset=0):
        return solid_from_wires(
            sketch_wires(sketch),
            thickness,
            offset=offset,
            xy_offset=xy_offset,
        )

    solar_wall_sketch = build_solar_wall_sketch()
    solar_top_sketch = build_solar_top_sketch()
    battery_holder_edge = (
        solar_wall_sketch.select("battery_holder_cutout").edges("<X and |Y").val()
    )
    battery_holder_top_y = max(vertex.Y for vertex in battery_holder_edge.Vertices())

    return (
        # The main solar cell wall that extends up from the top plate and wraps around the battery
        solid_from_sketch(
            solar_wall_sketch,
            solar_wall_thickness,
            offset=top_shell_height,
            xy_offset=-TOLERANCE,
        )
        # We add a support rib under the solar cell ceiling that doubles as a holder for the battery
        # below
        .union(
            cq.Workplane(
                "XZ",
                origin=(
                    battery_holder_edge.Center().x - TOLERANCE,
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
            .extrude(battery_holder_edge.Length())
        )
        # The face that the solar cell rests on top of, leaving a rectangular hole for the wires to
        # exit the cell and run down to the pcb
        .union(
            solid_from_sketch(
                solar_top_sketch,
                solar_top_thickness,
                offset=solar_top_z,
                xy_offset=-TOLERANCE,
            )
        )
        # We protect the edges of the solar cell with a thin, filleted wall that the cell will sit
        # flush within
        .union(
            solid_from_sketch(
                solar_top_sketch,
                solar_cell_thickness,
                offset=solar_ceiling_top_z,
                xy_offset=-TOLERANCE,
            )
            .faces(">Z")
            .fillet(TOP_FILLET_RADIUS)
            .cut(
                solid_from_wires(
                    feature_wire.get("solar_cell").get("F.Fab", []),
                    solar_cell_thickness,
                    offset=solar_ceiling_top_z,
                    xy_offset=TOLERANCE,
                )
            )
        )
    )


mounting_hole_wires = feature_wire.get("mounting_holes").get("drill", [])

board_outline_wire = largest_closed_wire(
    feature_wire.get(BOARD_FEATURE_NAME).get("Edge.Cuts", [])
)
board_outline_wires = [board_outline_wire] if board_outline_wire else []
outer_outline_wires = offset_wires(board_outline_wires, SKIRT_THICKNESS)
inner_outline_wires = offset_wires(board_outline_wires, TOLERANCE)


def build_bottom_plate_body():
    return solid_from_wires(board_outline_wires, PLATE_BOTTOM_THICKNESS)


def build_top_plate_body():
    return (
        profile_from_wires(outer_outline_wires)
        .extrude(top_shell_height)
        .faces(">Z")
        .fillet(TOP_FILLET_RADIUS)
        .cut(profile_from_wires(inner_outline_wires).extrude(skirt_height))
        .union(build_top_solar_component())
    )


def apply_footprint_cutouts(top_plate, bottom_plate, cutout_builders):
    for feature_name, build_top_cutout, build_bottom_cutout in cutout_builders:
        for footprint_angle, footprint_offset in footprint_placements[feature_name]:
            translation = (
                footprint_offset.x,
                footprint_offset.y,
                footprint_offset.z,
            )
            if build_top_cutout is not None:
                top_plate = top_plate.cut(
                    build_top_cutout()
                    .rotate((0, 0, 0), (0, 0, 1), footprint_angle)
                    .translate(translation)
                )
            if build_bottom_cutout is not None:
                bottom_plate = bottom_plate.cut(
                    build_bottom_cutout()
                    .rotate((0, 0, 0), (0, 0, 1), footprint_angle)
                    .translate(translation)
                )
    return top_plate, bottom_plate


feature_cut_builders = [
    (
        "battery_holder",
        build_battery_holder_cutout,
        lambda: build_bottom_cutout_from_top(build_battery_holder_cutout),
    ),
    (
        "capacitors",
        build_capacitor_cutout,
        lambda: build_bottom_cutout_from_top(build_capacitor_cutout),
    ),
    (
        "microcontroller",
        build_microcontroller_cutout,
        lambda: build_bottom_cutout_from_top(build_microcontroller_cutout),
    ),
    (
        "power_ic",
        build_power_ic_cutout,
        lambda: build_bottom_cutout_from_top(build_power_ic_cutout),
    ),
    (
        "power_switch",
        build_power_switch_cutout,
        lambda: build_bottom_cutout_from_top(build_power_switch_cutout),
    ),
    (
        "reset_button",
        build_reset_button_cutout,
        lambda: build_bottom_cutout_from_top(build_reset_button_cutout),
    ),
    (
        "resistors",
        build_resistor_cutout,
        lambda: build_bottom_cutout_from_top(build_resistor_cutout),
    ),
    (
        "solder_wires",
        build_solder_wire_cutout,
        lambda: build_bottom_cutout_from_top(build_solder_wire_cutout),
    ),
    ("inductors", build_inductor_cutout, None),
    ("kailh_switches", build_kailh_cutout, build_kailh_bottom_cutout),
]

top_mounting_hole_cutout = solid_from_wires(
    mounting_hole_wires,
    TOP_CUT_LOWER_THICKNESS,
    offset=skirt_height,
    xy_offset=TOLERANCE,
)
bottom_mounting_hole_cutout = solid_from_wires(
    mounting_hole_wires,
    PLATE_BOTTOM_THICKNESS,
    xy_offset=TOLERANCE,
)

top_plate_right, bottom_plate = apply_footprint_cutouts(
    build_top_plate_body().cut(build_board_cutout()).cut(top_mounting_hole_cutout),
    build_bottom_plate_body().cut(bottom_mounting_hole_cutout),
    feature_cut_builders,
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
