// Copyright 2026 The Lucky65 V2 Music Visualizer mod authors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Music visualizer host stream receiver + RGB matrix rendering.
// Host -> keyboard protocol: 32-byte raw HID reports (VIA raw HID endpoint):
//   byte 0    : MV_HID_MAGIC (0x4D)
//   byte 1    : low nibble = protocol version (MV_HID_VERSION)
//   byte 2..N : MV_BAND_COUNT band levels, 0..255 (low freq first)

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef RGB_MATRIX_ENABLE

#    define MV_HID_MAGIC   0x4D
#    define MV_HID_VERSION 0x01
#    define MV_BAND_COUNT  30

// Called with every raw HID report (via the multimode framework's
// via_command_user() hook). Returns true if the report was a (valid)
// music visualizer packet.
bool music_viz_process_hid(uint8_t *data, uint8_t length);

// Jump to the first visualizer mode, or cycle to the next one.
void music_viz_next_mode(void);

// Render one visualizer frame slice (called by the custom KB effects).
void music_viz_render_spectrum(uint8_t led_min, uint8_t led_max);
void music_viz_render_center(uint8_t led_min, uint8_t led_max);
void music_viz_render_pulse(uint8_t led_min, uint8_t led_max);

#endif
