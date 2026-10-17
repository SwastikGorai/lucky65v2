#!/usr/bin/env python3
"""Lucky65 V2 Music Visualizer - host streamer.

Captures system audio (WASAPI loopback on Windows), runs an FFT, reduces it
to N log-spaced band levels and streams them to the keyboard over the VIA
raw HID endpoint at ~60 Hz.

Protocol (32-byte raw HID reports, sent to usage page 0xFF60 / usage 0x61):
    byte 0     : 0x4D magic ('M')
    byte 1     : low nibble = protocol version (1)
    byte 2..31 : up to 30 band levels, 0..255, low frequency first

Usage examples:
    python musicviz.py --list-devices
    python musicviz.py                     # default output device loopback
    python musicviz.py --device Speakers   # device name substring
    python musicviz.py --preview           # console bars + streaming
    python musicviz.py --selftest          # no audio needed, tests the HID path
    python musicviz.py --dry-run --preview # audio analysis without keyboard
    python musicviz.py --probe sweep       # light each LED in turn (LED map debugging)
"""

import argparse
import sys
import threading
import time

import numpy as np

try:
    import hid
except Exception:  # pragma: no cover
    hid = None

try:
    import soundcard as sc
except Exception:  # pragma: no cover
    sc = None

VID = 0x342D
PID = 0xE407
MAGIC = 0x4D
PROTOCOL_VERSION = 0x01
REPORT_SIZE = 32
MAX_BANDS = 30

BLOCKS = "▁▂▃▄▅▆▇█"


# --------------------------------------------------------------------------
# HID transport
# --------------------------------------------------------------------------
class HidStreamer:
    """Sends 32-byte magic reports to the keyboard's VIA raw HID interface."""

    def __init__(self, dry_run=False, log=print):
        self.log = log
        self.dry_run = dry_run
        self.dev = None
        self.prefix = True  # hidapi convention: report id byte first

    def open(self):
        if self.dry_run:
            self.log("[hid] dry run - reports are not sent")
            return True
        if hid is None:
            self.log("[hid] python package 'hidapi' is not installed.")
            self.log("      Run: uv sync --locked --project musicviz-host (from the repo root)")
            return False
        infos = hid.enumerate(VID, PID)
        if not infos:
            self.log(
                f"[hid] keyboard not found (VID {VID:04X} PID {PID:04X}).\n"
                "      Make sure it is connected over USB and set to USB mode\n"
                "      (BL/2.4G modes do not forward raw HID)."
            )
            return False

        best = None
        for d in infos:
            usage_page = d.get("usage_page") or 0
            usage = d.get("usage") or 0
            if usage_page == 0xFF60:
                if usage == 0x61:
                    best = d
                    break
                if best is None:
                    best = d
        if best is None:
            self.log("[hid] VIA raw HID interface not found; connect in USB mode")
            return False
        path = best.get("path")

        try:
            if hasattr(hid, "Device"):  # hidapi >= 0.14 modern API
                self.dev = hid.Device(path=path)
            else:  # legacy 'hid' package API
                self.dev = hid.device()
                self.dev.open_path(path)
        except Exception as exc:
            self.log(f"[hid] failed to open raw HID interface: {exc}")
            return False

        product = best.get("product_string", "")
        self.log(f"[hid] opened raw HID interface '{product}' ({path!r})")
        return True

    def _write(self, payload):
        if self.dev is None:
            return
        try:
            if self.prefix:
                n = self.dev.write(bytes([0x00]) + payload)
                if n <= 0:
                    raise OSError("short write")
            else:
                if self.dev.write(payload) <= 0:
                    raise OSError("short write")
        except Exception:
            if self.prefix:  # retry without report-id prefix, then lock it in
                try:
                    if self.dev.write(payload) <= 0:
                        raise OSError("short write")
                    self.prefix = False
                    self.log("[hid] switched to prefix-less writes")
                except Exception as exc:
                    raise OSError(f"Keyboard disconnected: {exc}") from exc
            else:
                raise OSError("Keyboard write failed")

    def send(self, bands):
        if self.dry_run:
            return
        payload = bytes([MAGIC, PROTOCOL_VERSION]) + bytes(int(b) & 0xFF for b in bands)
        payload += bytes(REPORT_SIZE - len(payload))
        self._write(payload)

    def send_probe(self, index):
        """Probe command: light a single LED white (0xFF clears)."""
        if self.dry_run:
            return
        payload = bytes([MAGIC, PROTOCOL_VERSION | 0x80, index & 0xFF])
        payload += bytes(REPORT_SIZE - len(payload))
        self._write(payload)

    def control(self, command=0, value=0):
        if not 0 <= command <= 3 or not 0 <= value <= 255:
            raise ValueError("invalid control command")
        self._write(bytes([0x4E, 1, command, value]) + bytes(28))

    def read_settings(self):
        if self.dev is None:
            return None
        data = self.dev.read(32, 1)
        if (len(data) == 32 and list(data[:3]) == [0x4E, 1, 0x80]
                and data[3] <= 2 and data[4] <= 8 and data[5] <= 200 and data[6] <= 1):
            return tuple(data[3:7])
        return None

    def close(self):
        if self.dev is not None:
            try:
                self.dev.close()
            except Exception:
                pass


# --------------------------------------------------------------------------
# Audio capture + analysis
# --------------------------------------------------------------------------
class LoopbackCapture:
    """WASAPI loopback capture of a speaker via the 'soundcard' library."""

    def __init__(self, device_query, rate=None, log=print):
        self.log = log
        self.device_query = device_query
        self.rate = int(rate) if rate else 48000
        self.recorder = None
        self.mic = None
        self.channels = 2
        self.buffer = None
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.thread = None
        self.error = None

    def find_speaker(self):
        speakers = sc.all_speakers()
        if not speakers:
            return None
        if self.device_query:
            q = self.device_query.lower()
            hits = [s for s in speakers if q in s.name.lower()]
            return hits[0] if hits else None
        try:
            return sc.default_speaker()
        except Exception:
            return speakers[0]

    def open(self):
        speaker = self.find_speaker()
        if speaker is None:
            self.log("[audio] no matching output (speaker) device found")
            return False
        try:
            self.mic = sc.get_microphone(str(speaker.name), include_loopback=True)
        except Exception as exc:
            self.log(f"[audio] cannot open loopback of '{speaker.name}': {exc}")
            return False
        spk_channels = getattr(speaker, "channels", 2) or 2
        self.channels = 2 if spk_channels >= 2 else 1
        self.buffer = np.zeros(self.rate // 2, dtype=np.float32)  # 0.5 s ring
        try:
            self.recorder = self.mic.recorder(samplerate=self.rate, channels=self.channels, blocksize=1024)
            self.recorder.__enter__()
        except Exception as exc:
            self.log(f"[audio] failed to start loopback recorder: {exc}")
            return False
        self.thread = threading.Thread(target=self._run, name="loopback", daemon=True)
        self.thread.start()
        self.log(f"[audio] capturing loopback of '{speaker.name}' @ {self.rate} Hz, {self.channels} ch")
        return True

    def _run(self):
        while not self.stop_flag.is_set():
            try:
                data = self.recorder.record(numframes=1024)
            except Exception as exc:
                self.error = exc
                break
            mono = np.asarray(data, dtype=np.float32)
            if mono.ndim == 2:
                mono = mono.mean(axis=1)
            n = len(mono)
            with self.lock:
                if n >= len(self.buffer):
                    self.buffer[:] = mono[-len(self.buffer):]
                else:
                    self.buffer = np.roll(self.buffer, -n)
                    self.buffer[-n:] = mono

    def latest(self, n):
        if self.error is not None:
            raise RuntimeError(f"Audio capture stopped: {self.error}")
        with self.lock:
            if len(self.buffer) < n:
                return None
            return self.buffer[-n:].copy()

    def close(self):
        self.stop_flag.set()
        if self.recorder is not None:
            try:
                self.recorder.__exit__(None, None, None)
            except Exception:
                pass
        if self.thread is not None:
            self.thread.join(timeout=2.0)


class Analyzer:
    """FFT + log-band reduction + light tilt and global auto-boost."""

    def __init__(self, rate, bands, tilt_db=6.0, use_agc=True):
        self.rate = rate
        self.bands = bands
        self.nfft = 2048
        self.window = np.hanning(self.nfft).astype(np.float32)
        self.norm = 2.0 / float(self.window.sum())
        top = min(16000.0, rate / 2 - 100)
        edges = np.geomspace(20.0, top, bands + 1)
        freqs = np.fft.rfftfreq(self.nfft, 1.0 / rate)
        self.bins = []
        for i in range(bands):
            idx = np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0]
            if len(idx) == 0:
                idx = np.array([int(np.argmin(np.abs(freqs - edges[i])))])
            self.bins.append(idx)
        centers = np.sqrt(edges[:-1] * edges[1:])
        tilt = np.clip(3.0 * np.log2(np.maximum(centers, 40.0) / 125.0), 0.0, 9.0)
        self.tilt = (tilt * (tilt_db / 6.0)).astype(np.float32)
        self.use_agc = use_agc
        self.peak = 0.25
        self.boost = 1.0
        self.smooth = np.zeros(bands, dtype=np.float32)

    def analyze(self, mono):
        frame = mono[-self.nfft:]
        if len(frame) < self.nfft:
            return np.zeros(self.bands, dtype=np.uint8)
        spec = np.abs(np.fft.rfft(frame * self.window)) * self.norm
        vals = np.array([spec[idx].mean() for idx in self.bins], dtype=np.float32)
        db = 20.0 * np.log10(vals + 1e-7) + self.tilt
        v = np.clip((db + 66.0) / 60.0, 0.0, 1.0)  # -66..-6 dB -> 0..1
        v = np.where(v < 0.05, 0.0, v)  # noise gate: hiss must not become bars

        if self.use_agc:
            cur = float(np.max(v))
            self.peak = max(cur, self.peak * 0.995)
            target_boost = 1.0 / max(self.peak, 0.20)
            target_boost = float(np.clip(target_boost, 0.5, 3.5))
            self.boost += (target_boost - self.boost) * 0.04
            v = np.clip(v * self.boost, 0.0, 1.0)

        # temporal smoothing: fast attack, slower release. Raw per-frame FFT
        # levels jitter frame to frame; sending them unfiltered makes the
        # bars flicker, so blend rises quickly and falls gently.
        s = self.smooth
        alpha = np.where(v > s, 0.60, 0.20)
        s += (v - s) * alpha
        v = s

        return (v * 235.0).astype(np.uint8)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    p.add_argument("--device", default=None, help="output device name substring to capture (loopback)")
    p.add_argument("--bands", type=int, default=MAX_BANDS, help=f"number of bands (max {MAX_BANDS})")
    p.add_argument("--fps", type=float, default=60.0, help="report rate (default 60)")
    p.add_argument("--gain", type=float, default=1.0, help="manual gain multiplied after analysis")
    p.add_argument("--no-agc", action="store_true", help="disable the auto-boost")
    p.add_argument("--tilt", type=float, default=6.0, help="high-frequency tilt in dB (default 6, 0 disables)")
    p.add_argument("--rate", type=int, default=None, help="force capture samplerate")
    p.add_argument("--preview", action="store_true", help="draw band levels in the console")
    p.add_argument("--tui", action="store_true", help="interactive terminal controls")
    p.add_argument("--dry-run", action="store_true", help="analyze audio but do not open the keyboard")
    p.add_argument("--selftest", action="store_true", help="no audio: stream a synthetic pattern (HID path test)")
    p.add_argument("--probe", default=None, help="light one LED white to map LED indexes: an index or 'sweep'")
    p.add_argument("--duration", type=float, default=0.0, help="stop after N seconds (0 = run until Ctrl+C)")
    return p.parse_args()


def list_devices():
    if sc is None:
        print("soundcard is not installed; run uv sync --locked --project musicviz-host from the repo root")
        return
    speakers = sc.all_speakers()
    default = None
    try:
        default = sc.default_speaker()
    except Exception:
        pass
    print("Output devices (their loopback is what the visualizer captures):")
    for s in speakers:
        mark = " [default]" if default is not None and s.name == default.name else ""
        print(f"  {s.name}  ({getattr(s, 'channels', '?')} ch){mark}")


def preview_line(bands):
    return "".join(BLOCKS[min(7, int(b) * 8 // 256)] for b in bands)


def main():
    try:  # make the block characters render on Windows consoles
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = parse_args()
    if args.list_devices:
        list_devices()
        return 0

    if args.tui:
        if args.probe:
            raise SystemExit("Use --probe without --tui")
        from musicviz_tui import MusicApp
        MusicApp(args).run()
        return 0
    return run_stream(args)


def run_stream(args, panel=None):
    log = panel.log if panel else print

    bands_n = max(1, min(args.bands, MAX_BANDS))
    fps = max(10.0, min(args.fps, 120.0))
    period = 1.0 / fps

    hid_streamer = HidStreamer(dry_run=args.dry_run, log=log)
    if not hid_streamer.open() and not args.dry_run:
        return 1

    if args.probe is not None:
        sweep = str(args.probe).lower() == "sweep"
        idx = 0 if sweep else (int(args.probe) & 0xFF)
        try:
            while True:
                hid_streamer.send_probe(idx)
                print(f"\r[probe] LED {idx:3d} lit white" + ("  (Ctrl+C to stop)" if not sweep else ""), end="")
                time.sleep(0.5)
                if sweep:
                    idx = (idx + 1) % 70
        except KeyboardInterrupt:
            pass
        finally:
            hid_streamer.send_probe(0xFF)  # clear
            print("\n[probe] cleared")
        return 0

    capture = None
    analyzer = None
    if not args.selftest:
        if sc is None:
            log("soundcard is not installed; run uv sync --locked --project musicviz-host from the repo root")
            hid_streamer.close()
            return 1
        capture = LoopbackCapture(args.device, args.rate, log=log)
        try:
            opened = capture.open()
        except Exception:
            capture.close()
            hid_streamer.close()
            raise
        if not opened:
            capture.close()
            hid_streamer.close()
            return 1
        analyzer = Analyzer(capture.rate, bands_n, tilt_db=args.tilt, use_agc=not args.no_agc)
    else:
        log("[selftest] streaming a synthetic band pattern (no audio capture)")

    start = time.monotonic()
    next_tick = start
    last_stats = start
    frames = 0
    try:
        while True:
            if panel and panel.stop.is_set():
                break
            now = time.monotonic()
            if args.duration and (now - start) >= args.duration:
                break
            if now < next_tick:
                time.sleep(min(next_tick - now, 0.05))
                continue
            next_tick += period
            if panel:
                panel.exchange(hid_streamer, now)
                if analyzer:
                    analyzer.use_agc = panel.agc

            if args.selftest:
                t = now - start
                idx = np.arange(bands_n)
                v = np.abs(np.sin(idx * 0.42 + t * 3.0)) * (0.35 + 0.65 * abs(np.sin(t * 1.3)))
                levels = (v * 235.0).astype(np.uint8)
            else:
                mono = capture.latest(analyzer.nfft)
                if mono is None:
                    continue  # still filling the ring buffer
                levels = analyzer.analyze(mono)

            gain = panel.gain if panel else args.gain
            levels = np.clip(levels.astype(np.float32) * gain, 0, 255).astype(np.uint8)
            if panel:
                if panel.paused:
                    levels[:] = 0
                panel.levels = levels.copy()

            hid_streamer.send(levels[:bands_n])
            if panel:
                panel.last_audio_at = now
            frames += 1

            if args.preview and not panel:
                sys.stdout.write("\r" + preview_line(levels[:bands_n]))
                sys.stdout.flush()

            if now - last_stats >= 2.0:
                last_stats = now
                if not args.preview and not panel:
                    boost = getattr(analyzer, "boost", 1.0) if analyzer else 1.0
                    print(f"[stats] {frames / (now - start):5.1f} fps, boost {boost:.2f}x, max {int(max(levels)):3d}")
    except KeyboardInterrupt:
        pass
    finally:
        # idle the visualizer on exit
        try:
            hid_streamer.send([0] * bands_n)
        except Exception:
            pass
        if args.preview and not panel:
            sys.stdout.write("\n")
        if capture is not None:
            capture.close()
        hid_streamer.close()

    if frames == 0:
        log("no frames were sent")
        return 1
    log(f"done - sent {frames} frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
