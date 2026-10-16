#!/usr/bin/env bash
# Build the modded Lucky65 V2 music visualizer firmware.
#
#   bash firmware/build.sh
#
# Syncs the canonical keyboard sources (firmware/keyboards/lucky65v2) into
# the QMK build tree (qmk-firmware/, see firmware/setup.sh) and runs make.
#
# Environment overrides:
#   QMK_TREE      path to the vendor QMK tree   (default: <repo>/qmk-firmware)
#   GCC_ARM_DIR   GNU Arm 10.3 toolchain prefix (default: ~/tools/gcc-arm-none-eabi-10.3-2021.10)
#   QMK_PIP_BIN   directory containing the qmk CLI (default: ~/.local/bin)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${QMK_TREE:-$ROOT/qmk-firmware}"
TOOLCHAIN="${GCC_ARM_DIR:-$HOME/tools/gcc-arm-none-eabi-10.3-2021.10}"
QMK_PIP_BIN="${QMK_PIP_BIN:-$HOME/.local/bin}"

if [ ! -d "$TREE/keyboards" ]; then
    echo "QMK tree not found at $TREE - run 'bash firmware/setup.sh' first" >&2
    exit 1
fi
if [ ! -x "$TOOLCHAIN/bin/arm-none-eabi-gcc" ]; then
    echo "ARM toolchain not found at $TOOLCHAIN (set GCC_ARM_DIR; see README)" >&2
    exit 1
fi

export PATH="$QMK_PIP_BIN:$TOOLCHAIN/bin:$PATH"

# canonical sources -> build tree
rm -rf "$TREE/keyboards/lucky65v2"
cp -r "$ROOT/firmware/keyboards/lucky65v2" "$TREE/keyboards/lucky65v2"

cd "$TREE"
echo "Using $(arm-none-eabi-gcc --version | head -n1)"
echo "Using $(qmk --version | head -n1) for repository tooling"
exec make lucky65v2:via "$@"
