// To improve accuracy for small holes, we reduce the minimum arc segment size.
$fs = 0.1;
mode = "preview"; // [preview, top, bottom]

// Intermediate assets are generated from the KiCad design files using generate-case.sh.
case_dir = "case/";
plate_back = str(case_dir, "cweep-B_Plate.dxf");
plate_front = str(case_dir, "cweep-F_Plate.dxf");
pcb = str(case_dir, "cweep.stl");

// SendCutSend has a cut tolerance of +/- 0.005 inches (0.127mm) for mild steel.
cut_tolerance = 0.127;
// SendCutSends says powder typically adds ~0.002"-0.005" per side.
powder_coat_thickness = 0.127;

top_plate_clearance = cut_tolerance;
/*
  Kailh hot-swap sockets are designed to clip into a 1.2mm thick plate:
  https://docs.keeb.io/choc-stabs#other-random-notes
*/
top_plate_thickness = 1.2;

pcb_thickness = 1.6;

bottom_plate_color = "#a7a89d";
/* 
  We want the bottom plate to sit flush with the the thickest component on the back, the Kailh
  hot-swap sockets. I will be using A36/1008 Mild Steel from SendCutSend, and the nearest desired
  size without going over 1.6mm is 1.5mm (0.059 inches).
*/
bottom_plate_stock_thickness = 1.5;
bottom_plate_clearance = powder_coat_thickness + cut_tolerance;
bottom_plate_final_thickness = bottom_plate_stock_thickness + 2 * powder_coat_thickness;

module top_plate() {
  offset(delta=-top_plate_clearance)
    import(file=plate_front);
}

module bottom_plate() {
  offset(delta=-bottom_plate_clearance)
    import(file=plate_back);
}

module pcb() {
  import(file=pcb);
}

if (mode == "preview") {
  translate(v=[0, 0, -bottom_plate_final_thickness - 0.001])
    color(bottom_plate_color)
      linear_extrude(height=bottom_plate_final_thickness)
        offset(r=powder_coat_thickness)
          bottom_plate();

  %pcb();

  translate(v=[0, 0, pcb_thickness - 0.089])
    linear_extrude(height=top_plate_thickness)
      top_plate();
} else if (mode == "top") {
  top_plate();
} else if (mode == "bottom") {
  bottom_plate();
}
