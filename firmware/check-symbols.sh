#!/usr/bin/env bash
# Verify that a built firmware contains the music visualizer symbols.
#
#   bash firmware/check-symbols.sh [path/to/firmware.elf]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${QMK_TREE:-$ROOT/qmk-firmware}"
export PATH="$HOME/tools/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH"

ELF="${1:-$TREE/.build/lucky65v2_via.elf}"
echo "=== size ==="
arm-none-eabi-size "$ELF"
echo "=== mod symbols ==="
arm-none-eabi-nm "$ELF" | grep -E "music_viz|via_command_user_kb|MV_SPECTRUM|MV_CENTER|MV_PULSE" || echo "NO SYMBOLS FOUND"
