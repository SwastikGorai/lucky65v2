# musicviz-host

The desktop side of the lucky65 music visualizer: captures whatever your PC is
playing (WASAPI loopback), turns it into 30 log-spaced band levels and streams
them to the keyboard over raw HID at ~60 fps. Windows-first, nothing exotic.

## Install

```powershell
uv sync
```

That's it — uv creates the venv (fetching python 3.12 per `.python-version`
if you don't have it) and installs exactly what's in `uv.lock`.

Audio capture uses [`soundcard`](https://pypi.org/project/soundcard/) for the
WASAPI loopback — pure ctypes, no PortAudio wrestling. Heads-up if you have
MSYS2's python on PATH: it makes venvs with a POSIX layout (`bin/` instead of
`Scripts/`) that won't run from PowerShell. uv sidesteps all of that.

## Use

```powershell
run-musicviz.cmd --list-devices     # show output devices
run-musicviz.cmd                    # stream (default output device loopback)
run-musicviz.cmd --preview          # also draw bars in the console
run-musicviz.cmd --device Speakers  # capture a specific device by substring
run-musicviz.cmd --selftest         # no audio: synthetic pattern to the board
run-musicviz.cmd --dry-run --preview  # audio only, no keyboard needed
```

Put the keyboard in a visualizer mode first (**Fn + Del**, or cycle with
RGB_MOD) — the effect renders whatever the host sends.

| flag            | meaning                                                      |
|-----------------|--------------------------------------------------------------|
| `--device NAME` | substring match on an output device to capture its loopback  |
| `--bands N`     | 1-30 bands (default 30)                                      |
| `--fps F`       | report rate, default 60                                      |
| `--gain F`      | fixed gain multiplier applied after analysis                 |
| `--no-agc`      | disable the automatic loudness normalisation                 |
| `--tilt DB`     | high-frequency tilt, default 6 dB, `0` disables              |
| `--preview`     | console bar display                                          |
| `--dry-run`     | skip the keyboard, useful with `--preview`                   |
| `--duration S`  | stop after S seconds (0 = run until Ctrl+C)                  |

On exit the app sends a zero-level report so the effect returns to idle.

## Sanity check

No hardware needed:

```powershell
uv run python test_analyzer.py
```

Feeds the analyzer synthetic tones (100 Hz / 1 kHz / 8 kHz), silence and a
very quiet signal, and checks the right bands light up and the AGC behaves.

## Autostart (optional)

Drop a shortcut to `run-musicviz.cmd` into `shell:startup`.

## Troubleshooting

- **`keyboard not found`** — the keyboard must be in **USB mode** (not
  Bluetooth/2.4G) and plugged in; raw HID only exists over USB.
- **`failed to start loopback recorder`** — pick a concrete output device via
  `--device`; exclusive-mode audio apps can block loopback.
- **Bars look flat/quiet** — raise `--tilt`, try `--gain 1.5`, or just let the
  AGC settle for a second or two.
