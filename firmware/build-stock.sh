#!/usr/bin/env bash
# Build a pristine (unmodified) Lucky65 V2 firmware as a recovery image.
#
#   bash firmware/build-stock.sh
#
# Uses the vendor sources in vendor/lucky65v2 and copies the result to
# stock/lucky65v2_via_stock.bin.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${QMK_TREE:-$ROOT/qmk-firmware}"
PRISTINE="$ROOT/vendor/lucky65v2"
STAGE="$TREE/keyboards/lucky65v2_stock"

if [ ! -d "$PRISTINE" ]; then
    echo "pristine source not found at $PRISTINE" >&2
    exit 1
fi
if [ ! -d "$TREE/keyboards" ]; then
    echo "QMK tree not found at $TREE - run 'bash firmware/setup.sh' first" >&2
    exit 1
fi

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

rm -rf "$STAGE"
cp -r "$PRISTINE" "$STAGE"
# QMK requires <keyboard-dir-name>.h / .c / .json
mv "$STAGE/lucky65v2.c" "$STAGE/lucky65v2_stock.c"
mv "$STAGE/lucky65v2.h" "$STAGE/lucky65v2_stock.h"
mv "$STAGE/lucky65v2.json" "$STAGE/lucky65v2_stock.json"

export PATH="$HOME/.local/bin:$HOME/tools/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH"
cd "$TREE"
rm -rf .build/obj_lucky65v2_stock .build/obj_lucky65v2_stock_via
make lucky65v2_stock:via

mkdir -p "$ROOT/stock"
cp ".build/lucky65v2_stock_via.bin" "$ROOT/stock/lucky65v2_via_stock.bin"
echo "Stock recovery image: $ROOT/stock/lucky65v2_via_stock.bin"
