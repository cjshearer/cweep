#!/usr/bin/env bash
# Mirror KiCad PCB from clipboard and place result back to clipboard
# Usage: ./mirror_pcb_clipboard.sh

# Function to detect and use the appropriate clipboard command
get_clipboard_cmd() {
  if command -v xclip &>/dev/null; then
    echo "xclip -selection clipboard -o"
  elif command -v wl-paste &>/dev/null; then
    echo "wl-paste"
  elif command -v pbpaste &>/dev/null; then
    echo "pbpaste"
  else
    echo "ERROR: No clipboard tool found (xclip, wl-paste, or pbpaste)" >&2
    exit 1
  fi
}

set_clipboard_cmd() {
  if command -v xclip &>/dev/null; then
    echo "xclip -selection clipboard -i"
  elif command -v wl-copy &>/dev/null; then
    echo "wl-copy"
  elif command -v pbcopy &>/dev/null; then
    echo "pbcopy"
  else
    echo "ERROR: No clipboard tool found (xclip, wl-copy, or pbcopy)" >&2
    exit 1
  fi
}

# Launch nix develop environment and run the mirroring operation
nix develop --command bash -c '
  # Get clipboard commands
  CLIPBOARD_GET="'"$(get_clipboard_cmd)"'"
  CLIPBOARD_SET="'"$(set_clipboard_cmd)"'"
  
  # Create temporary files
  TEMP_INPUT=$(mktemp)
  TEMP_OUTPUT=$(mktemp)
  
  # Get clipboard content
  eval "$CLIPBOARD_GET" > "$TEMP_INPUT"
  
  # Apply transformations
  sed -E '\''
    # 1. Replace right-labeled components with left equivalents
    s/([A-Za-z0-9_]+)_R([0-9]+)/\1_L\2/g;
    # 2a. Flip layer: B.XXX -> F.XXX.placeholder
    s/\(layer "B\.([A-Za-z0-9_]+)"\)/\(layer "F.\1.placeholder"\)/g;
    # 2b. Flip layer: F.XXX -> B.XXX
    s/\(layer "F\.([A-Za-z0-9_]+)"\)/\(layer "B.\1"\)/g;
    # 2c. Flip layer: F.XXX.placeholder -> B.XXX
    s/\(layer "F\.([A-Za-z0-9_]+)\.placeholder"\)/\(layer "B.\1"\)/g;
  '\'' "$TEMP_INPUT" > "$TEMP_OUTPUT"
  
  # Write back to clipboard
  cat "$TEMP_OUTPUT" | eval "$CLIPBOARD_SET"
  
  # Clean up
  rm "$TEMP_INPUT" "$TEMP_OUTPUT"
  
  echo "PCB mirrored and copied to clipboard"
'