#!/usr/bin/env bash
#
# generate-case.sh
#
# Generates inputs for the case design from the PCB file, creating a bottom and top plate suitable
# for 3D printing, or CNC machining.

usage() {
  cat <<'EOF'
Usage: ./generate-case.sh [options]

Options:
  -h Show this help message and exit
  -d Enable development mode: automatically regenerate case inputs and watch for changes
EOF
}

while getopts "hd" opt; do
  case $opt in
    h) usage; exit 0 ;;
    d) ENV="dev" ;;
    *) usage; exit 1 ;;
  esac
done      


mkdir -p case

function extract_case_outlines() {
  kicad-cli pcb export dxf cweep.kicad_pcb \
    --drill-shape-opt 0 \
    --mode-multi \
    --output case \
    --output-units mm \
    -l "User.1,User.2"
}

function extract_pcb_model() {
  kicad-cli pcb export stl cweep.kicad_pcb \
  --output case/cweep.stl
}

function build_case_plate() {
  local mode="$1"
  if [[ "$mode" != "bottom" && "$mode" != "top" ]]; then
    echo "Error: Please specify 'bottom' or 'top' as an argument."
    exit 1
  fi

  openscad -D "mode=\"${mode}\"" -o case/cweep_plate_"${mode}".dxf cweep.scad
  cd case || exit 1
  dxf-fix cweep_plate_"${mode}".dxf cweep_plate_"${mode}".dxf
  mv reconstruction_overlay.png cweep_plate_"${mode}"_reconstruction.png
  cd - || exit 1
}

function run_with_prefix() {
  local prefix="$1"
  shift
  "$@" 2>&1 | sed "s/^/\x1b[35m[${prefix}]: \x1b[0m/"
}

if [[ "$ENV" == "dev" ]]; then
  # This stl extraction is not needed for case generation, but it's useful to have while developing.
  # However, it takes a while to run, so we only do it on the first run in dev mode.
  extract_pcb_model
  export -f extract_case_outlines build_case_plate run_with_prefix
  trap "exit 1" SIGINT
  find cweep.kicad_pcb | entr -s '
    flock case/.case_gen.lock -c "
      run_with_prefix case_outlines extract_case_outlines
      # this is just to trigger OpenSCAD to re-render if the GUI is open
      touch cweep.scad
    "
  ' &
  find cweep.scad case/cweep-*.dxf | entr -ps '
    flock case/.case_gen.lock -c "
      run_with_prefix case_bottom build_case_plate bottom &
      run_with_prefix case_top build_case_plate top
    "
  '
  trap - SIGINT
else
  extract_case_outlines || exit $?
  run_with_prefix bottom_plate build_case_plate bottom &
  run_with_prefix top_plate build_case_plate top &
  wait
fi