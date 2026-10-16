#!/usr/bin/env bash
# One-time setup: fetch the vendor QMK tree this board needs and apply the
# two build patches. Run from the repo root:
#
#   bash firmware/setup.sh
#
# Downloads the WB32/itarze QMK fork (GPL-2.0) that the Lucky65 family ships
# with, extracted from:
#   https://github.com/gskycraig/QMK_Lucky65
# (same vendor framework as the official Weikav source drop - it vendors the
#  keyboards/multimode wireless stack and ChibiOS so the tree builds as-is).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${QMK_TREE:-$ROOT/qmk-firmware}"
ZIP_URL="https://github.com/gskycraig/QMK_Lucky65/archive/refs/heads/main.zip"

if [ ! -d "$TREE" ]; then
    echo "Downloading the vendor QMK tree (~150 MB, this takes a while)..."
    curl -L --retry 20 --retry-delay 5 --retry-all-errors --fail -o /tmp/qmk_lucky65.zip "$ZIP_URL"
    rm -rf /tmp/qmk_lucky65_extract
    mkdir -p /tmp/qmk_lucky65_extract
    python3 -m zipfile -e /tmp/qmk_lucky65.zip /tmp/qmk_lucky65_extract
    mv /tmp/qmk_lucky65_extract/QMK_Lucky65-main "$TREE"
    rm -rf /tmp/qmk_lucky65_extract /tmp/qmk_lucky65.zip
    echo "Tree extracted to $TREE"
else
    echo "Tree already present at $TREE"
fi

cd "$TREE"
for p in "$ROOT"/firmware/patches/*.patch; do
    name="$(basename "$p")"
    if patch -p1 -R --dry-run --silent < "$p" >/dev/null 2>&1; then
        echo "already applied: $name"
    elif patch -p1 --dry-run --silent --forward < "$p" >/dev/null 2>&1; then
        patch -p1 --silent < "$p"
        echo "applied: $name"
    else
        echo "WARNING: cannot apply $name cleanly (already modified?)" >&2
    fi
done

cat <<'EOF'

Tree ready. Remaining prerequisites (one-time, see README):
  1. GNU Arm Embedded 10.3-2021.10 toolchain in ~/tools
  2. qmk CLI:        pip install --user --break-system-packages qmk
  3. tree deps:      pip install --user --break-system-packages -r <tree>/requirements.txt

Then build with:  bash firmware/build.sh
EOF
