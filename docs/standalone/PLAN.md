# Standalone desktop release status

**Included release:** `build/desktop/release/Lucky65Music.exe`.
The app, modified firmware, and updater are tracked through explicit ignore
exceptions; no local build is needed for the normal quick start.
**Next verification:** test the built EXE on a clean Windows x64 machine, then verify
physical keyboard behavior and an actual sign-in cycle with startup enabled.

## Delivered

- Single portable, windowed Windows EXE with bundled Python and native libraries.
- Neubrutalist GUI with effect, color, sensitivity, brightness, AGC, pause, and
  audio-output controls. CLI and TUI share the same streamer.
- Minimalist 67-key Lucky65 preview, refreshed around 30 fps. It estimates
  Breathing and Bottom-up bar using outgoing audio and reported keyboard settings,
  including the firmware's 40 ms attack / 180 ms release envelope.
- Tray menu, automatic device retry, atomic preference saves, rotating logs,
  duplicate-instance protection, and optional per-user Windows startup.
- Fixed the reproduced combobox `KeyError: 'popdown'` freeze. Refresh callbacks
  recover after transient failures rather than permanently stopping.

## Build and files

Install uv, then run `.\musicviz-host\build-desktop.ps1` from the repo root in
PowerShell. It uses locked uv build dependencies and PyInstaller. A diagnostic
folder build remains available with `-Folder`. Only the release EXE and modified
firmware `.bin` are tracked under `build/`; other generated files remain ignored.
The portable app deliverable is the single EXE above. See the
[technical guide](../technical-guide.md) for installation and firmware setup.

Settings and logs live under `%LOCALAPPDATA%/Lucky65Music`. Startup is off by
default. Re-enable startup after moving the EXE to update its registered path.
Firmware flashing remains a separate operation.

## Verification

These are recorded development-machine results, not checks performed by cloning
the repository or guarantees about a separately obtained executable.

- All 11 desktop/TUI automated tests passed, including real Tk dropdown focus,
  refresh recovery, preview layout/envelope/row fill/timeout, preferences,
  reconnect, shutdown, mutex behavior, and mocked startup registration.
- Analyzer checks passed during desktop implementation.
- Actual Windows loopback capture and worker shutdown passed on the development
  machine with keyboard output disabled.
- Final single-file release passed its isolated synthetic GUI smoke test with
  exit code 0. The GUI layout was visually inspected.

## Remaining limits

Clean-machine, physical-keyboard matching, device-removal scenarios, and actual
Windows sign-in validation remain outstanding. The lighting preview is not LED
telemetry: drift phase, physical LED mapping, and indicator overlays may differ.
Custom VIA colors and non-music effects are explicitly marked unavailable.
The EXE is unsigned; code signing, installers, auto-updates, and other operating
systems are deferred.
