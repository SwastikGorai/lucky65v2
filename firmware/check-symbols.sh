#!/usr/bin/env bash
set -euo pipefail
ELF="${1:?Usage: check-symbols.sh firmware.elf}"
arm-none-eabi-size "$ELF"
symbols="$(arm-none-eabi-nm --defined-only "$ELF")"
for name in music_viz_process_hid music_viz_render_breathing music_viz_render_bar music_viz_next_mode via_command_user_kb; do
    if ! grep -Eq " [Tt] ${name}$" <<< "$symbols"; then
        echo "Missing required firmware symbol: $name" >&2
        exit 1
    fi
done
