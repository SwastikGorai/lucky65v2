#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${QMK_TREE:?Set QMK_TREE to the container vendor tree}"
REV=103601dfcfbf03db103898a90fd0243f3293e297
if [ ! -d "$TREE/keyboards" ]; then
    archive="$(mktemp)"
    trap 'rm -f "$archive"' EXIT
    curl -fL --retry 5 "https://codeload.github.com/gskycraig/QMK_Lucky65/tar.gz/$REV" -o "$archive"
    mkdir -p "$TREE"
    tar -xzf "$archive" --strip-components=1 -C "$TREE"
    printf '%s\n' "$REV" > "$TREE/.vendor-revision"
fi
test "$(cat "$TREE/.vendor-revision")" = "$REV"
cd "$TREE"
for p in "$ROOT"/firmware/patches/*.patch; do
    if patch -p1 -R --dry-run --silent < "$p" >/dev/null 2>&1; then
        echo "Already applied: $(basename "$p")"
    elif patch -p1 --dry-run --silent --forward < "$p" >/dev/null 2>&1; then
        patch -p1 --silent < "$p"
    else
        echo "Required patch cannot be applied: $p" >&2
        exit 1
    fi
done
