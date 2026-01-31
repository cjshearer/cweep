// Use generate-case.sh to extract geometry from cweep.kicad_pcb
case_directory = "case";

/*
  SendCutSend has a cut tolerance of +/- 0.005 inches (0.127mm) for mild steel.
  SendCutSends says powder typically adds ~0.002"-0.005" per side.
*/
cut_tolerance = 0.127;
min_powder_coat_thickness = 0.0508;
max_powder_coat_thickness = 0.127;
avg_powder_coat_thickness = (
  min_powder_coat_thickness + max_powder_coat_thickness
) / 2;

top_solar_show = true;
top_cover_show = true;
top_switch_show = true;
top_spacer_show = true;
pcb_show = true;
bottom_plate_show = true;

top_solar_color = "#c2c2c280";
top_cover_color = "#5994dc80";
top_switch_color = "#b4dbd280";
top_spacer_color = "#d8c85280";
pcb_color = "#8d0084ff";
bottom_plate_color = "#c2c2c280";

plate_top_solar_dxf = str(case_directory, "/cweep-F_Plate_Solar.dxf");
plate_top_cover_dxf = str(case_directory, "/cweep-F_Plate_Cover.dxf");
plate_top_switch_dxf = str(case_directory, "/cweep-F_Plate_Switch.dxf");
plate_top_spacer_dxf = str(case_directory, "/cweep-F_Plate_Spacer.dxf");
pcb_stl = str(case_directory, "/cweep.stl");
plate_bottom_dxf = str(case_directory, "/cweep-B_Plate.dxf");
plate_outline_dxf = str(case_directory, "/cweep-Plate_Outline.dxf");
plate_holes_dxf = str(case_directory, "/cweep-Plate_Holes.dxf");

/*
  The bottom plate will be cut from 16 gauge A36/1008 mild steel.
*/
plate_top_solar_thickness = 5.01;
plate_top_cover_thickness = 0.82;
plate_top_switch_thickness = 1.25;
plate_top_spacer_thickness = 1;
pcb_thickness = 1.6;
plate_bottom_thickness = 1.52;
plate_bottom_final_thickness = plate_bottom_thickness + max_powder_coat_thickness * 2;

// We add a small gap when displaying the transparent PCB to avoid visible z-fighting
gap_between_pcb = pcb_show ? 0.0008 : 0;
z_bottom = 0;
z_pcb = z_bottom + plate_bottom_final_thickness + gap_between_pcb;
z_top_spacer = z_pcb + pcb_thickness - 0.089 + gap_between_pcb;
z_top_switch = z_top_spacer + plate_top_spacer_thickness + gap_between_pcb;
z_top_cover = z_top_switch + plate_top_switch_thickness + gap_between_pcb;
z_top_solar = z_top_cover + plate_top_cover_thickness + gap_between_pcb;

/* [Hidden] */

// To improve accuracy for small holes, we reduce the minimum arc segment size.
$fs = 0.1;

module plate(
  plate_dxf,
  outline_offset = 0,
  holes_offset = 0,
  feature_offset = cut_tolerance,
  powder_coated = false,
  thickness,
  height,
  color_value
) {
  // If only one component is being shown, render in 2D for DXF export.
  // If multiple components are shown, render in 3D for visualization and STL export.
  // If the PCB is shown, we always render in 3D to show the STL model.
  render_3d = (
    (pcb_show ? 2 : 0) + (bottom_plate_show ? 1 : 0) + (top_spacer_show ? 1 : 0) + (top_switch_show ? 1 : 0) + (top_cover_show ? 1 : 0)
  ) > 1;

  if (render_3d) {
    color(color_value)
      translate([0, 0, height])
        linear_extrude(height=thickness)
          offset(r=powder_coated ? avg_powder_coat_thickness : 0)
            difference() {
              offset(delta=outline_offset)
                import(file=plate_outline_dxf);
              offset(delta=holes_offset)
                import(file=plate_holes_dxf);
              offset(delta=feature_offset)
                import(file=plate_dxf);
            }
  } else {
    difference() {
      offset(delta=outline_offset)
        import(file=plate_outline_dxf);
      offset(delta=holes_offset)
        import(file=plate_holes_dxf);
      offset(delta=feature_offset)
        import(file=plate_dxf);
    }
  }
}

if (bottom_plate_show) {
  plate(
    plate_dxf=plate_bottom_dxf,
    outline_offset=-avg_powder_coat_thickness,
    holes_offset=avg_powder_coat_thickness,
    feature_offset=cut_tolerance + max_powder_coat_thickness,
    powder_coated=true,
    thickness=plate_bottom_final_thickness,
    height=z_bottom,
    color_value=bottom_plate_color
  );
}

if (pcb_show) {
  color(pcb_color)
    translate([0, 0, z_pcb])
      %import(file=pcb_stl);
}

if (top_spacer_show) {
  plate(
    plate_dxf=plate_top_spacer_dxf,
    thickness=plate_top_spacer_thickness,
    height=z_top_spacer,
    color_value=top_spacer_color
  );
}

if (top_switch_show) {
  plate(
    plate_dxf=plate_top_switch_dxf,
    thickness=plate_top_switch_thickness,
    height=z_top_switch,
    color_value=top_switch_color
  );
}

if (top_cover_show) {
  plate(
    plate_dxf=plate_top_cover_dxf,
    thickness=plate_top_cover_thickness,
    height=z_top_cover,
    color_value=top_cover_color
  );
}

if (top_solar_show) {
  plate(
    plate_dxf=plate_top_solar_dxf,
    thickness=plate_top_solar_thickness,
    height=z_top_solar,
    color_value=top_solar_color
  );
}
