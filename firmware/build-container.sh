#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
target="${1:?Expected modified or stock}"
case "$target" in
    modified) source="$ROOT/firmware/keyboards/lucky65v2"; artifact=lucky65v2_via ;;
    stock) source="$ROOT/vendor/lucky65v2"; artifact=lucky65v2_via_stock ;;
    *) echo "Unknown target: $target" >&2; exit 1 ;;
esac
clean="${2:-}"
[[ -z "$clean" || "$clean" == --clean ]] || { echo "Unknown option: $clean" >&2; exit 1; }
TREE="/cache/$target/qmk"
export CCACHE_DIR="/cache/$target/ccache"
mkdir -p "$TREE" "$CCACHE_DIR" "/out/$target"
# Serialize use of a target's writable tree, including source synchronization.
exec 9>"/cache/$target/build.lock"
flock 9
rsync -rlc --delete --exclude=.build --exclude=keyboards/lucky65v2 /opt/qmk/ "$TREE/"
mkdir -p "$TREE/keyboards/lucky65v2"
rsync -rlc --delete "$source/" "$TREE/keyboards/lucky65v2/"
fingerprint="$( { printf '%s\n' "${BUILD_IMAGE_ID:-}"; cat /opt/build-environment.txt; find "$ROOT/firmware" -type f ! -path '*/keyboards/*' -print0 | sort -z | xargs -0 sha256sum; find "$source" -type f -print0 | sort -z | xargs -0 sha256sum; } | sha256sum | cut -d' ' -f1)"
if [[ "$clean" == --clean || ! -f "/cache/$target/inputs" || "$(cat "/cache/$target/inputs")" != "$fingerprint" ]]; then
    rm -rf "$TREE/.build"
fi
# No old success artifacts should survive a failed attempt.
rm -f "/out/$target/$artifact.bin" "/out/$target/$artifact.elf" "/out/$target/metadata.json"
cd "$TREE"
make lucky65v2:via USE_CCACHE=yes -j"$(nproc)"
arm-none-eabi-size .build/lucky65v2_via.elf
# WB32FQ95xB's linker script also enforces its 128 KiB flash / 28 KiB RAM.
bytes="$(stat -c %s .build/lucky65v2_via.bin)"
if (( bytes == 0 || bytes > 131072 )); then
    echo "Invalid firmware size: $bytes bytes (flash limit 131072)" >&2
    exit 1
fi
if [[ "$target" == modified ]]; then
    bash "$ROOT/firmware/check-symbols.sh" .build/lucky65v2_via.elf
fi
cp .build/lucky65v2_via.bin "/out/$target/$artifact.bin"
cp .build/lucky65v2_via.elf "/out/$target/$artifact.elf"
python3 - "$target" "$artifact" "$fingerprint" <<'PY'
import datetime, hashlib, json, os, pathlib, subprocess, sys
target, artifact, fingerprint = sys.argv[1:]
out = pathlib.Path('/out') / target
metadata = dict(target=target, inputs_sha256=fingerprint,
                vendor_revision=pathlib.Path('/opt/qmk/.vendor-revision').read_text().strip(),
                image=os.environ.get('BUILD_IMAGE_ID'),
                toolchain=subprocess.check_output(['arm-none-eabi-gcc', '--version'], text=True).splitlines()[0],
                built_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                artifacts={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (out / (artifact + '.bin'), out / (artifact + '.elf'))})
(out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
PY
printf '%s\n' "$fingerprint" > "/cache/$target/inputs"
echo "Exported $target firmware to build/firmware/$target/"
