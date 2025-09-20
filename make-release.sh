#!/usr/bin/env bash
# make-release.sh
# Prepares a release by updating the version number and sha1 in the PCB file.
# Usage: ./make-release.sh major|minor|patch

current_version=$(grep -oP 'cjshearer/cweep\\n\K[0-9]+\.[0-9]+\.[0-9]+' cweep.kicad_pcb | head -1)
current_hash=$(grep -oP 'cjshearer/cweep\\n[0-9]+\.[0-9]+\.[0-9]+ - \K[0-9a-f]+' cweep.kicad_pcb | head -1)

echo "Current version: $current_version ($current_hash)"

if ! [[ "$1" =~ ^(major|minor|patch)$ ]]; then
  echo "Invalid argument: $1. Use major, minor, or patch."
  exit 1
fi

new_version=$(
  IFS='.' read -r major minor patch <<< "$current_version"
  case $1 in
    major) ((major++)); minor=0; patch=0 ;;
    minor) ((minor++)); patch=0 ;;
    patch) ((patch++)) ;;
    *) echo "Invalid argument: $1. Use major, minor, or patch." ; exit 1 ;;
  esac
  echo "$major.$minor.$patch"
)
new_hash=$(git rev-parse --short HEAD)

echo "Updating to $new_version ($new_hash)"

sed -i "s#cjshearer/cweep\\\n$current_version - $current_hash#github.com/cjshearer/cweep\\\n$new_version - $new_hash#" cweep.kicad_pcb

git add cweep.kicad_pcb
git commit -m "build: $current_version -> $new_version"