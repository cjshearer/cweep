#!/usr/bin/env bash

mkdir -p images

kicad-cli pcb export dxf cweep.kicad_pcb \
  --mode-single \
  --output images/cweep-Edge_Cuts-drill.dxf \
  --output-units mm \
  -l "Edge.Cuts"

kicad-cli pcb export dxf cweep.kicad_pcb \
  --drill-shape-opt 0 \
  --mode-multi \
  --output images \
  --output-units mm \
  -l "Edge.Cuts,F.Cuts,B.Cuts,F.Fill,B.Fill"

# kicad-cli pcb export stl cweep.kicad_pcb \
#   --output images/cweep.stl