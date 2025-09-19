#!/usr/bin/env bash
# generate-images.sh
# Regenerates the pictures in the README from the KiCad files.
# Requires kicad-cli to be installed and in your PATH.
# Usage: ./generate-images.sh

mkdir -p images

kicad-cli sch export svg cweep.kicad_sch \
  --output images \
  --theme "Solarized Dark (Schematic only)"

# # Generate SVGs of the front and back PCB layers
for side in F B; do
  kicad-cli pcb export svg cweep.kicad_pcb \
    --output images/pcb-${side}.svg \
    -l ${side}.Cu,${side}.Mask,${side}.Paste,${side}.SilkS,${side}.Fab,Edge.Cuts \
    --mode-single \
    --fit-page-to-board \
    --exclude-drawing-sheet \
    $( [ "$side" = "B" ] && echo "--mirror" )

  # Add a background color to the SVG (Solarized Dark)
  sed -i 's-</title>-</title>\n  <rect xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" fill="#002B36"/>-' images/pcb-${side}.svg
done

# # Generate 3D renders of the top and bottom of the PCB
for side in top bottom; do
  kicad-cli pcb render cweep.kicad_pcb \
  --output images/pcb-3d-$side.png \
  --height 1200 \
  --width 1400 \
  --background opaque \
  --floor \
  --light-bottom 0.2 \
  --light-camera 0.6 \
  --light-side 0.6 \
  --light-side-elevation 50 \
  --light-top 0.9 \
  --pan "0,1,0" \
  --perspective \
  --preset follow_plot_settings \
  --quality basic \
  --rotate "'-20,0,10'" \
  --side $side \
  --zoom $(
    declare -A zoom=(
      [top]=0.95
      [bottom]=0.98
    ) && echo "${zoom[$side]}"
  )
done