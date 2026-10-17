# Technical guide

Commands below run from the repository root unless stated otherwise.
For features and quick start, see [README](../README.md).

## What a fresh checkout contains

The following ready-to-use files are tracked and included in a clone:

| File | Purpose |
|---|---|
| `build/desktop/release/Lucky65Music.exe` | Portable Windows app |
| `build/firmware/modified/lucky65v2_via.bin` | Music firmware |
| `stock/lucky65v2_via_stock.bin` | Stock recovery firmware |
| `tools/wb32/wb32-dfu-updater_cli.exe` | Windows flashing tool |
| `tools/wb32/libusb-1.0.dll` | Updater USB dependency |

Updater licenses and source metadata are included beside it. These files have
explicit `.gitignore` exceptions; other tools, build intermediates, and virtual
environments remain ignored. Source builds are optional and replace the tracked
release files locally. No uv, Docker, or Python installation is needed to use
the included app and firmware.

## Standalone Windows app

The included EXE is ready to run without installing anything. To rebuild the
portable GUI on Windows x64, install
[uv](https://docs.astral.sh/uv/getting-started/installation/)
(`winget install --id astral-sh.uv -e`, then open a new terminal).
Run from the repo root:

```powershell
.\musicviz-host\build-desktop.ps1
```

The output is `build/desktop/release/Lucky65Music.exe`. Double-click it to open
the desktop controls and begin streaming. uv manages Python for the build;
recipients can copy and run the single EXE without installing Python or uv. Connect the
keyboard in USB mode with the updated firmware already flashed.

The GUI uses a neubrutalist layout with bold borders, offset shadows, and flat
colors. It provides effect/color selection, sensitivity, brightness, auto gain,
pause/resume, output-device selection, and a minimalist 67-key Lucky65 lighting
preview. It mirrors Breathing or Bottom-up bar using outgoing audio and the
keyboard's reported color, brightness, and RGB state, with the firmware's
40 ms attack / 180 ms release smoothing. The preview refreshes around 30 fps.
It is a host-side estimate, not LED telemetry: drift phase, physical LED mapping,
and status indicators can differ. Custom VIA colors and non-music RGB effects
are labeled as unavailable rather than guessed. Select a music effect
to enable music lighting. Host preferences save automatically; keyboard lighting
is read from the board rather than overwritten at startup. Closing the window
hides it to the tray; use the tray menu to reopen, pause, or quit.

**Start with Windows** is off by default. Enable it in the GUI to launch in the
tray at sign-in. Keep the EXE at a stable location; after moving it, disable and
re-enable the checkbox. Disable startup before deleting the app. Startup uses
the current user's registry entry and requires no administrator privileges.

Settings and rotating diagnostic logs live in `%LOCALAPPDATA%\Lucky65Music`.
Invalid settings use safe defaults and require **Save preferences** before the
file is replaced. The app retries unavailable devices every two seconds.
No audio recordings are saved. Close VIA while using live keyboard controls.

Run `Lucky65Music.exe --demo` for synthetic lighting controls without hardware.
`--smoke-test` performs a short hidden demo and exits. The executable is unsigned;
Windows may show a reputation warning. First launch extracts its bundled runtime
to a temporary directory. Clean-machine and physical-keyboard validation remain
outstanding; development-machine packaging and audio checks are recorded in the
[standalone plan](standalone/PLAN.md).

For a diagnostic folder build, use `.\musicviz-host\build-desktop.ps1 -Folder`
from the repo root. Folder builds, intermediates, and generated notices are
ignored; only the release EXE is tracked. Dependency notices are also bundled
inside the EXE.

## Firmware build from PowerShell

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) for the
Python host. On Windows, you can use `winget install --id astral-sh.uv -e`, then
open a new terminal. uv manages the host's Python version and virtual environment.
There is no requirements.txt or manual pip installation step.

Install Docker Desktop and start its **Linux container engine**. No Windows ARM
toolchain, WSL commands, privileged containers or USB passthrough are needed.

```powershell
.\firmware\build-docker.ps1          # modified firmware
.\firmware\build-docker.ps1 -Stock   # recovery firmware
.\firmware\build-docker.ps1 -Clean   # clean only the modified build output
.\firmware\build-docker.ps1 -Stock -Clean
```

The first build downloads the image, GNU Arm Embedded **10.3-2021.10**, and the
vendor QMK tree. The Dockerfile pins its base image digest and toolchain SHA-256;
`firmware/pyproject.toml` and `firmware/uv.lock` pin Python dependencies, and `setup.sh` pins the vendor
revision. Required patches fail the build if they cannot be applied or verified.

The image includes uv 0.9.15 and runs `uv sync --locked` into an isolated QMK
environment using its pinned Python 3.11.11. Docker handles firmware dependencies;
you do not need to install QMK's Python packages on Windows. The host has its own
`musicviz-host/pyproject.toml` and `uv.lock` for its separate audio/TUI environment.
The launcher uses `uv run --locked`, so normal launches do not rewrite the lockfile.

When intentionally changing dependencies, use `uv add --project musicviz-host PACKAGE`
for the host, or edit `firmware/pyproject.toml` and run
`uv lock --project firmware --python 3.11` for the build environment. Commit both
the project file and its lockfile, and rebuild Docker after firmware dependency
changes. The build environment follows uv's [Docker setup](https://docs.astral.sh/uv/guides/integration/docker/).

Sources are mounted read-only. The `lucky65-firmware-cache` Docker volume keeps
separate stock/modified QMK trees and compiler caches. Content-based syncing
includes deletions and reverts; changed inputs invalidate that target's object
output, while ccache reuses matching compilation results. `-Clean` retains the
compiler cache and the other target. Builds targeting the same tree serialize.
The vendor's generated version header embeds build time, so incremental builds
can still recompile a few files.

After a successful build, artifacts are exported under `build/firmware/`.
Only the modified `.bin` is tracked there; ELF files, metadata, and rebuilt stock
outputs are ignored. The separately tracked stock binary is under `stock/`:

| Target | Binary | Other output |
|---|---|---|
| Modified | `modified/lucky65v2_via.bin` | `.elf`, `metadata.json` |
| Stock | `stock/lucky65v2_via_stock.bin` | `.elf`, `metadata.json` |

Metadata records the image ID, vendor revision, compiler, input fingerprint and
artifact hashes. Both builds run size checks; the modified build also requires
the music rendering and HID-hook symbols. Flashing is a separate operation.

## Get the WB32 updater (Windows)

The repo includes `tools/wb32/wb32-dfu-updater_cli.exe` and its USB DLL. Keep them
together; installation is unnecessary for this bundled copy. Source metadata and
licenses are in the same directory. The updater package was SHA-256 verified.

To install a separate copy instead, the
[official Westberry project](https://github.com/WestberryTech/wb32-dfu-updater)
directs Windows users to its prebuilt
[MSYS2 package](https://packages.msys2.org/packages/mingw-w64-x86_64-wb32-dfu-updater).

1. Install [MSYS2](https://www.msys2.org/) and open its **MSYS2 MINGW64** terminal.
2. Update packages with `pacman -Syu`. If prompted to close the terminal, reopen
   MINGW64 and run that command again to finish the update.
3. Install the updater and its dependencies:

   ```bash
   pacman -S mingw-w64-x86_64-wb32-dfu-updater
   ```

With the default MSYS2 installation, the executable is at
`C:\msys64\mingw64\bin\wb32-dfu-updater_cli.exe`. Keep it in that directory so
its dependency DLLs remain available. From PowerShell, verify the installation:

```powershell
& 'C:\msys64\mingw64\bin\wb32-dfu-updater_cli.exe' --help
```

The examples below use the repo's bundled updater. If you prefer the MSYS2 copy,
replace `.\tools\wb32\wb32-dfu-updater_cli.exe` with
`& 'C:\msys64\mingw64\bin\wb32-dfu-updater_cli.exe'`, adjusting the path if needed.

If Windows does not recognize the keyboard in bootloader mode, the official
project provides a Windows driver in its
[`driver` directory](https://github.com/WestberryTech/wb32-dfu-updater/tree/master/driver).
Download the source ZIP, extract it, and follow the project's instructions to
run `winusb_install.bat` from the driver package, accepting Windows elevation
if required.

## Detect before flashing

Close the music app and VIA, put the keyboard in USB mode, then hold **Esc**
while reconnecting its USB cable to enter the WB32 bootloader. From the repo root:

```powershell
.\tools\wb32\wb32-dfu-updater_cli.exe --list
```

`--list` only enumerates DFU-capable devices; it does not write firmware. Expect
a device entry before flashing. `Not found device!` means no bootloader device
was detected: check the data cable, bootloader entry, and Windows driver above.
The keyboard appearing as a normal typing device does not establish DFU readiness.
Disconnect other DFU devices to avoid ambiguity. Alternatively, `--devnum N`
selects the device number reported by `--list` for the current connection.

## Flash and use

> **DO AT YOUR OWN RISK. I am not responsible for bricked keyboards or any damage caused by flashing or using this firmware.**

1. Use the included modified firmware, or optionally rebuild it with
   `.\firmware\build-docker.ps1`. Close the app and VIA, hold
   **Esc** while plugging in the keyboard, and confirm detection using `--list`
   above before flashing:

   ```powershell
   .\tools\wb32\wb32-dfu-updater_cli.exe -D .\build\firmware\modified\lucky65v2_via.bin
   ```

2. Reconnect in **USB mode** (Bluetooth/2.4G cannot carry the audio reports).
   With Python package manager `uv` installed, start the host from the repo root:

   ```powershell
   cd musicviz-host
   uv sync --locked
   .\run-musicviz.cmd --tui
   ```

3. Select **Breathing** or **Bottom-up bar** in the TUI, or hold **Fn + Right
   Ctrl** and press **`\`**. Play music on your PC and leave the host running.

Existing VIA keymaps live in EEPROM and can override the compiled defaults. If
Fn + Del still selects music after upgrading, remap that key to Delete in VIA;
keep Fn + `\` assigned to RGB Mode for the chord. Saved old Spectrum/Center mode
slots become Breathing/Vertical Bar; the removed Pulse slot falls back to
Breathing at startup.

## Local terminal controls

The TUI runs locally in your terminal and adjusts the running audio stream and
keyboard. Use the mouse or **Tab / Shift+Tab**, then **Enter**, to activate buttons.
Enlarge the terminal if controls are clipped (100 columns × 32 rows is tested).

| Control | What it does |
|---|---|
| Sensitivity − / +, or `-` / `+` | Adjust audio gain from 0.1× to 4× in 0.1 steps. Higher values make quieter audio brighter. |
| Auto gain | Toggle automatic loudness normalization. |
| Breathing / Bottom-up bar | Select a music effect and enable RGB. |
| Next color | Cycle the seven fixed colors and color drift. |
| Dimmer / Brighter | Adjust maximum LED brightness from 0 to 200 in steps of 10. |
| Pause, or Space | Send zero levels so the music effect fades out; press again to resume. |
| Q | Quit and send zero levels before closing the connection. |

Sensitivity controls the audio response, not key actuation. The meter displays
outgoing audio levels. The panel reads keyboard settings four times per second,
so physical shortcut changes also appear on screen.

From `musicviz-host`, these commands cover common setups:

```powershell
.\run-musicviz.cmd --tui --gain 1.5          # start with higher sensitivity
.\run-musicviz.cmd --list-devices           # list audio outputs
.\run-musicviz.cmd --tui --device Speakers  # capture a matching output
.\run-musicviz.cmd --tui --dry-run --selftest # demo without keyboard or audio
.\run-musicviz.cmd --preview                # stream with simple console bars
```

Live keyboard controls and drift require the updated firmware. Close VIA while
using the TUI. If keyboard buttons stay disabled, check USB mode and the flashed
firmware; after a stream error, quit and restart the host.

TUI changes do not write EEPROM: host sensitivity and auto gain reset when the
app restarts, and keyboard settings revert to saved values when the board
restarts. Drift selected with Fn + Enter also resets on reboot. For all CLI
options and troubleshooting, see the [host guide](../musicviz-host/README.md).

## Recovery

To restore the vendor-based stock firmware, quit the music app and VIA, then
hold **Esc** while reconnecting the keyboard. From the repo root, confirm a DFU
device appears before writing anything:

```powershell
.\tools\wb32\wb32-dfu-updater_cli.exe --list
```

If detection succeeds and no other DFU devices are connected, flash:

```powershell
.\tools\wb32\wb32-dfu-updater_cli.exe -D .\stock\lucky65v2_via_stock.bin
```

The command uses the tracked `stock/lucky65v2_via_stock.bin`, which is included
in a clone. To rebuild stock from the vendor source, run
`.\firmware\build-docker.ps1 -Stock`; the rebuilt output is a separate file at
`build/firmware/stock/lucky65v2_via_stock.bin`. Reconnect normally after flashing; the
custom music effects and desktop lighting controls require the modified firmware.
Flashing stock firmware does not guarantee that saved VIA/EEPROM settings reset.
The same **DO AT YOUR OWN RISK** flashing disclaimer applies.

## Verification

```powershell
cd musicviz-host
uv sync --locked
uv run --locked python test_analyzer.py
uv run --locked python -m unittest discover -p 'test_*.py'
cd ..
# Requires a previous successful firmware build to create lucky65-firmware:local.
docker run --rm --mount "type=bind,source=$PWD,target=/src,readonly" lucky65-firmware:local python /src/firmware/tests/run.py
```

The firmware test compiles the actual rendering/HID code and shortcut preamble
against QMK stubs. It checks constant-input settling, attack/release, frame-rate
independence, frame slices, row fill, brightness zero, silence, timeout, timer
wrap, saved modes, Windows/Mac shortcuts, color drift, and control validation.
The headless TUI tests exercise live controls and clean shutdown without hardware.
The firmware test also runs locally with Python
and GCC: `python firmware/tests/run.py`.

For build-workflow regression checks (both targets, clean/incremental builds,
source deletion/revert, artifact hashes, and deliberately failed builds), use
disposable volumes so the normal build cache stays intact:

```powershell
docker run --rm --mount "type=bind,source=$PWD,target=/src,readonly" --mount type=volume,target=/cache --mount type=volume,target=/out lucky65-firmware:local python /src/firmware/tests/test_build.py
```

Physical LED alignment must be checked after flashing: send controlled levels
47, 94, 141, 188 and 235 to fill one through five rows. Use
`.\musicviz-host\run-musicviz.cmd --probe sweep` from the repo root to identify any incorrect LED coordinates before
changing `g_led_config`. The existing source has a known possible mismatch
between the Caps Lock LED and its documented coordinate; software tests cannot
establish the physical row map.

## Protocol

32-byte raw HID (usage page `0xFF60`, usage `0x61`): `0x4D`, version `1`,
30 band levels (0–255, bass first). Probe packets use version `0x81` and an LED
index in byte 2 (`0xFF` clears). The audio packet format is unchanged.
Live settings use separate `0x4E` control packets, documented in the
[host protocol reference](../musicviz-host/README.md#live-control-protocol).
