// To improve accuracy for small holes, we reduce the minimum arc segment size.
$fs = 0.1;

show_pcb = true;

// We want the bottom plate to sit flush with the the thickest component the back, the Kailh hot-swap sockets.
bottom_plate_thickness = 0.063 * 2.54 * 10; // 0.063 inches in mm
pcb_thickness = 1.6;
// The bottom plate will be made of stainless steel.
bottom_plate_color = "#74017cff";
// To ensure electrical clearance, the stainless steel bottom plate's cutouts are enlarged.
bottom_plate_offset = 0.2;
// Kailh hot-swap sockets are designed to clip into a 1.2mm thick plate:
// https://docs.keeb.io/choc-stabs#other-random-notes
top_plate_thickness = 1.2;

pcb_outline_with_drill_holes = "images/cweep-Edge_Cuts-drill.dxf";
pcb_outline = "images/cweep-Edge_Cuts.dxf";
front_cuts = "images/cweep-F_Cuts.dxf";
back_cuts = "images/cweep-B_Cuts.dxf";
front_fill = "images/cweep-F_Fill.dxf";
back_fill = "images/cweep-B_Fill.dxf";

pcb = "images/cweep.stl";

// For pin clearance, the bottom plate needs all holes cutout except vias, while the top plate only
// needs the screw holes. We use a side-effect of fileting to close small via holes:
// https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Transformations#offset
module plate(close_holes_below = 0.5) {
  difference() {
    offset(-close_holes_below / 2)
      offset(delta=(close_holes_below / 2))
        import(file=pcb_outline_with_drill_holes);
  }
}

module top_plate() {
  linear_extrude(height=top_plate_thickness) {
    difference() {
      plate();
      import(file=front_cuts);
    }
  }
}

module bottom_plate() {
  linear_extrude(height=bottom_plate_thickness)
    difference() {
      plate();
      offset(delta=bottom_plate_offset) {
        import(file=back_cuts);
      }
    }
}

module pcb() {
  import(file=pcb);
}

translate(v=[0, 0, -bottom_plate_thickness])
  color(bottom_plate_color) {
    bottom_plate();
  }

if (show_pcb) %pcb();

translate(v=[0, 0, pcb_thickness - 0.1]) {
  top_plate();
}

// /* [Rendering options] */
// // Show placeholder PCB in OpenSCAD preview
// show_pcb = false;
// // Lid mounting method
// lid_model = "cap"; // [cap, inner-fit]
// // Conditional rendering
// render = "case"; // [all, case, lid]

// /* [Dimensions] */
// // Height of the PCB mounting stand-offs between the bottom of the case and the PCB
// standoff_height = 5;
// // PCB thickness
// pcb_thickness = 1.6;
// // Bottom layer thickness
// floor_height = 1.2;
// // Case wall thickness
// wall_thickness = 1.2;
// // Space between the top of the PCB and the top of the case
// headroom = 0;

// /* [M2.5 screws] */
// // Outer diameter for the insert
// insert_M2_5_diameter = 3.27;
// // Depth of the insert
// insert_M2_5_depth = 3.75;

// /* [Hidden] */
// $fa=$preview ? 10 : 4;
// $fs=0.2;
// inner_height = floor_height + standoff_height + pcb_thickness + headroom;

// module wall (thickness, height) {
//     linear_extrude(height, convexity=10) {
//         difference() {
//             offset(r=thickness)
//                 children();
//             children();
//         }
//     }
// }

// module bottom(thickness, height) {
//     linear_extrude(height, convexity=3) {
//         offset(r=thickness)
//             children();
//     }
// }

// module lid(thickness, height, edge) {
//     linear_extrude(height, convexity=10) {
//         offset(r=thickness)
//             children();
//     }
//     translate([0,0,-edge])
//     difference() {
//         linear_extrude(edge, convexity=10) {
//                 offset(r=-0.2)
//                 children();
//         }
//         translate([0,0, -0.5])
//          linear_extrude(edge+1, convexity=10) {
//                 offset(r=-1.2)
//                 children();
//         }
//     }
// }

// module box(wall_thick, bottom_layers, height) {
//     if (render == "all" || render == "case") {
//         translate([0,0, bottom_layers])
//             wall(wall_thick, height) children();
//         bottom(wall_thick, bottom_layers) children();
//     }

//     if (render == "all" || render == "lid") {
//         translate([0, 0, height+bottom_layers+0.1])
//         lid(wall_thick, bottom_layers, lid_model == "inner-fit" ? headroom-2.5: bottom_layers) 
//             children();
//     }
// }

// module mount(drill, space, height) {
//     translate([0,0,height/2])
//         difference() {
//             cylinder(h=height, r=(space/2), center=true);
//             cylinder(h=(height*2), r=(drill/2), center=true);

//             translate([0, 0, height/2+0.01])
//                 children();
//         }

// }

// module connector(min_x, min_y, max_x, max_y, height) {
//     size_x = max_x - min_x;
//     size_y = max_y - min_y;
//     translate([(min_x + max_x)/2, (min_y + max_y)/2, height/2])
//         cube([size_x, size_y, height], center=true);
// }

// module pcb() {
//     thickness = 1.6;

//     color("#009900")
//     difference() {
//         linear_extrude(thickness) {
//             polygon(points = [[120.87502,82.65], [120.87502,34.75]]);
//         }
//     translate([0, 0, -1])
//     linear_extrude(thickness+2) 
//         polygon(points = [[12.875,90.25], [12.875,26.1575]]);

//     translate([62.4, 16.65, -1])
//         cylinder(thickness+2, 1.1000000000000014, 1.1000000000000014);
//     translate([55, 88.65, -1])
//         cylinder(thickness+2, 1.0999999999999943, 1.0999999999999943);
//     translate([96.6, 87.25, -1])
//         cylinder(thickness+2, 1.0999999999999943, 1.0999999999999943);
//     translate([26.8, 24.05, -1])
//         cylinder(thickness+2, 1.1000000000000014, 1.1000000000000014);
//     translate([109.4, 29.25, -1])
//         cylinder(thickness+2, 1.1000000000000014, 1.1000000000000014);
//     translate([35.4, 75.25, -1])
//         cylinder(thickness+2, 1.0999999999999943, 1.0999999999999943);
//     }
// }

// module case_outline() {
//     polygon(points = [[12.875,92.25], [10.875,90.25], [10.875,26.1575], [12.875,24.1575]]);
// }

// module Insert_M2_5() {
//     translate([0, 0, -insert_M2_5_depth])
//         cylinder(insert_M2_5_depth, insert_M2_5_diameter/2, insert_M2_5_diameter/2);
//     translate([0, 0, -0.3])
//         cylinder(0.3, insert_M2_5_diameter/2, insert_M2_5_diameter/2+0.3);
// }

// rotate([render == "lid" ? 180 : 0, 0, 0])
// scale([1, -1, 1])
// translate([-11.875, -58.20375, 0]) {
//     pcb_top = floor_height + standoff_height + pcb_thickness;

//     difference() {
//         box(wall_thickness, floor_height, inner_height) {
//             case_outline();
//         }

//     translate([0, 0, -1])
//     #linear_extrude(floor_height+2, convexity=10) 
//         polygon(points = [[122.87502,82.65], [122.87502,34.75], [120.87502,32.75]]);

//     translate([0, 0, -1])
//     #linear_extrude(floor_height+2, convexity=10) 
//         polygon(points = [[120.87502,84.65], [122.87502,82.65]]);

//     }

//     if (show_pcb && $preview) {
//         translate([0, 0, floor_height + standoff_height])
//             pcb();
//     }

//     if (render == "all" || render == "case") {
//         // H6 [('M2.5', 2.5)]
//         translate([62.4, 16.65, floor_height])
//         mount(2.2, 4.2, standoff_height)
//             Insert_M2_5();
//         // H3 [('M2.5', 2.5)]
//         translate([55, 88.65, floor_height])
//         mount(2.2, 4.2, standoff_height)
//             Insert_M2_5();
//         // H2 [('M2.5', 2.5)]
//         translate([96.6, 87.25, floor_height])
//         mount(2.2, 4.2, standoff_height)
//             Insert_M2_5();
//         // H5 [('M2.5', 2.5)]
//         translate([26.8, 24.05, floor_height])
//         mount(2.2, 4.2, standoff_height)
//             Insert_M2_5();
//         // H1 [('M2.5', 2.5)]
//         translate([109.4, 29.25, floor_height])
//         mount(2.2, 4.2, standoff_height)
//             Insert_M2_5();
//         // H4 [('M2.5', 2.5)]
//         translate([35.4, 75.25, floor_height])
//         mount(2.2, 4.2, standoff_height)
//             Insert_M2_5();
//     }
// }
