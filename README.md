# lucky65 music visualizer

Music visualizer mod for the Weikav Lucky65 V2. A python app captures system
audio and streams frequency bands to the keyboard over USB; the firmware
renders them as three new RGB effects. USB only, no extra hardware.

Modes: `MV_SPECTRUM` (bars), `MV_CENTER` (grow from middle), `MV_PULSE`
(loudness). Cycle with RGB_MOD or press **Fn + Del**.

## Use

1. Hold **Esc** while plugging the keyboard in, then flash:

   ```powershell
   wb32-dfu-updater_cli.exe -D qmk-firmware\.build\lucky65v2_via.bin
   ```

2. Run the app:

   ```powershell
   cd musicviz-host
   uv sync
   run-musicviz.cmd
   ```

3. Press **Fn + Del**, play music.

## Build

Board runs a vendor QMK fork; the build tree is fetched separately (WSL/Linux):

```bash
bash firmware/setup.sh     # one-time: fetch tree, apply patches
bash firmware/build.sh     # -> qmk-firmware/.build/lucky65v2_via.bin
```

Needs the GNU Arm 10.3 toolchain in `~/tools` and `pip install --user
--break-system-packages qmk`. `bash firmware/build-stock.sh` builds the
unmodified firmware (recovery image in `stock/`).

## Recovery

Bootloader is in ROM: hold Esc while plugging in, reflash
`stock/lucky65v2_via_stock.bin`.

## Protocol

32-byte raw HID (usage page `0xFF60`, usage `0x61`): `0x4D`, version,
30 band levels (0-255, bass first).