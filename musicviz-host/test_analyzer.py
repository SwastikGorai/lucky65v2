#!/usr/bin/env python3
"""Offline sanity checks for the analyzer + protocol constants.

No audio device, no keyboard needed:

    python test_analyzer.py

Exits non-zero and prints the failures if anything is off.
"""

import sys

import numpy as np

from musicviz import MAX_BANDS, MAGIC, PROTOCOL_VERSION, REPORT_SIZE, Analyzer

RATE = 48000


def tone(freq, seconds=0.5, amp=0.5):
    t = np.arange(int(RATE * seconds)) / RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def band_for(freq):
    edges = np.geomspace(20, min(16000, RATE / 2 - 100), MAX_BANDS + 1)
    return int(np.searchsorted(edges, freq) - 1)


def main():
    failures = []

    # protocol layout: magic + version byte + 30 bands == one 32 byte report
    if 2 + MAX_BANDS != REPORT_SIZE:
        failures.append(f"protocol layout mismatch: 2+{MAX_BANDS} != {REPORT_SIZE}")
    if MAGIC != 0x4D or PROTOCOL_VERSION != 0x01:
        failures.append("magic/version drifted from the firmware protocol")

    # silence must stay dark (and AGC must not amplify it into bars)
    silent = Analyzer(RATE, MAX_BANDS)
    for _ in range(10):
        levels = silent.analyze(np.zeros(2048, dtype=np.float32))
    if int(levels.max()) > 40:
        failures.append(f"silence should be dark, max={int(levels.max())}")

    # pure tones must land in their own frequency band
    for freq in (100, 1000, 8000):
        a = Analyzer(RATE, MAX_BANDS)
        lv = None
        for _ in range(5):  # a few frames so the smoothing settles
            lv = a.analyze(tone(freq))
        peak_band = int(np.argmax(lv))
        expected = band_for(freq)
        if abs(peak_band - expected) > 1:
            failures.append(f"{freq} Hz peaked in band {peak_band}, expected ~{expected}")
        if int(lv.max()) < 60:
            failures.append(f"{freq} Hz too weak after analysis: {int(lv.max())}")

    # AGC should lift a quiet signal over ~a second of frames
    a = Analyzer(RATE, MAX_BANDS)
    quiet = tone(440, amp=0.004)
    first = int(a.analyze(quiet).max())
    for _ in range(120):
        later = int(a.analyze(quiet).max())
    if later < 60 or later <= first:
        failures.append(f"AGC did not lift quiet signal: first={first}, later={later}")

    if failures:
        print("FAIL")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: analyzer banding, silence floor, AGC and protocol layout all good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
