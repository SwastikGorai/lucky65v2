# musicviz-host

The desktop side of the lucky65 music visualizer: captures whatever your PC is
playing (WASAPI loopback), turns it into 30 log-spaced band levels and streams
them to the keyboard over raw HID at ~60 fps. Windows-first, nothing exotic.

## Install

For the standalone desktop GUI, build from the repository root with
`.\musicviz-host\build-desktop.ps1`, then run
`build\desktop\release\Lucky65Music.exe`. The EXE bundles Python and its
dependencies; recipients do not need uv or Python installed. Install uv using
the source installation steps below only if rebuilding. The ready-to-use EXE
and modified firmware are included at the paths documented in the main README.
For source-based
GUI development, run `uv run --locked python musicviz_gui.py` from this directory.
Use `--demo` to try the controls without audio or keyboard hardware.

The window closes to a tray icon with Open, Pause/Resume, and Quit. Optional
**Start with Windows** launches in the tray at sign-in and is available in the
packaged EXE. Preferences save automatically under `%LOCALAPPDATA%\Lucky65Music`;
keyboard lighting remains controlled by the current board settings until changed
in the GUI. See the [desktop guide](../docs/technical-guide.md#standalone-windows-app).

### Source installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first:
`winget install --id astral-sh.uv -e` on Windows, then open a new terminal.
Run the following from `musicviz-host` (use `cd musicviz-host` from the repo root).

```powershell
uv sync --locked
```

That's it — uv creates the venv (fetching python 3.12 per `.python-version`
if you don't have it) and installs exactly what's in `uv.lock`.
The launcher also uses `uv run --locked` to keep dependency versions fixed.
No separate pip install or virtual-environment activation is needed. To add a
dependency deliberately, run `uv add PACKAGE` here and commit `pyproject.toml`
and `uv.lock` together.

Audio capture uses [`soundcard`](https://pypi.org/project/soundcard/) for the
WASAPI loopback — pure ctypes, no PortAudio wrestling. Heads-up if you have
MSYS2's python on PATH: it makes venvs with a POSIX layout (`bin/` instead of
`Scripts/`) that won't run from PowerShell. uv sidesteps all of that.

## Use

For the local terminal panel, run from this directory:

```powershell
.\run-musicviz.cmd --tui
```

Use the buttons (mouse or Tab/Enter) to adjust sensitivity (0.1–4×), auto gain,
Breathing/Bottom-up bar, color, brightness, and pause while audio is playing.
`+`/`-` adjust sensitivity, Space pauses, and Q quits. Higher sensitivity makes
quiet audio brighter; it does not change the keyboard's key actuation.
The meter shows outgoing audio levels. Hardware settings refresh four times
per second, including changes made with the keyboard shortcuts.

For color drift and live keyboard controls, first follow the
[firmware build and flash instructions](../README.md#quick-start-windows), then
connect in USB mode. Firmware paths in those instructions are relative to the
repository root. In either music effect,
**Fn + Enter** cycles red → yellow → green → cyan → blue → pink → white →
**color drift** → red. Drift takes 12 seconds around the hue wheel; audio still
controls brightness. Normal RGB effects keep their existing color cycle.

TUI adjustments are temporary (no EEPROM writes); sensitivity/auto gain reset
when the host restarts, and keyboard settings reset when the board restarts.
Drift selected from the keyboard also resets on reboot. Use `--gain 1.5` to
choose a starting sensitivity. Close VIA while using this raw HID controller.
If controls receive no reply, the panel disables the keyboard buttons and
shows a USB/firmware hint. After a stream error, quit and restart the app.

Try the complete panel without hardware or audio:

```powershell
.\run-musicviz.cmd --tui --dry-run --selftest
uv run --locked python -m unittest test_tui
```

### Live control protocol

The existing 32-byte audio reports are unchanged. Control requests use
`[0x4E, 1, command, value, ...zero padding]`. Command 0 reads state, 1 selects
effect (1 breathing, 2 bar, also enables RGB), 2 selects color (0–6 presets,
7 drift), and 3 sets brightness (0–200). Valid requests receive
`[0x4E, 1, 0x80, effect, color, brightness, enabled, ...zero padding]`.
Effect 0 means another RGB effect; color 8 means a custom VIA color. Invalid
requests are consumed without changing settings or replying. Host writes
include the HID report-ID byte 0 before the 32-byte payload.

### Command-line use

```powershell
.\run-musicviz.cmd --list-devices     # show output devices
.\run-musicviz.cmd                    # stream (default output device loopback)
.\run-musicviz.cmd --preview          # also draw bars in the console
.\run-musicviz.cmd --device Speakers  # capture a specific device by substring
.\run-musicviz.cmd --selftest         # no audio: synthetic pattern to the board
.\run-musicviz.cmd --dry-run --preview  # audio only, no keyboard needed
```

Put the keyboard in a visualizer mode first: hold **Fn + Right Ctrl**, then
press **`\`**. This toggles Breathing and Vertical Bar. Both use the strongest
received band; Fn + `\` alone continues cycling normal RGB effects.

| flag            | meaning                                                      |
|-----------------|--------------------------------------------------------------|
| `--device NAME` | substring match on an output device to capture its loopback  |
| `--bands N`     | 1-30 bands (default 30)                                      |
| `--fps F`       | report rate, default 60                                      |
| `--gain F`      | fixed gain multiplier applied after analysis                 |
| `--no-agc`      | disable the automatic loudness normalisation                 |
| `--tilt DB`     | high-frequency tilt, default 6 dB, `0` disables              |
| `--preview`     | console bar display                                          |
| `--tui`         | interactive terminal controls and live audio meter           |
| `--dry-run`     | skip the keyboard, useful with `--preview`                   |
| `--duration S`  | stop after S seconds (0 = run until Ctrl+C)                  |

On exit the app sends a zero-level report so the effect fades to dark.

## Sanity check

No hardware needed:

```powershell
uv run --locked python test_analyzer.py
uv run --locked python -m unittest discover -p 'test_*.py'
```

Feeds the analyzer synthetic tones (100 Hz / 1 kHz / 8 kHz), silence and a
very quiet signal, and checks the right bands light up and the AGC behaves.

## Autostart (optional)

For the packaged GUI, enable **Start with Windows** in the app. For the TUI,
you can instead put a shortcut to `run-musicviz.cmd --tui` in `shell:startup`;
this requires uv and the source checkout to remain available. Choose one startup
method to avoid duplicate streamers.

## Troubleshooting

- **`keyboard not found`** — the keyboard must be in **USB mode** (not
  Bluetooth/2.4G) and plugged in; raw HID only exists over USB.
- **`failed to start loopback recorder`** — pick a concrete output device via
  `--device`; exclusive-mode audio apps can block loopback.
- **Bars look flat/quiet** — raise `--tilt`, try `--gain 1.5`, or just let the
  AGC settle for a second or two.
