// Copyright 2026 The Lucky65 V2 Music Visualizer mod authors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Music visualizer for the Weikav Lucky65 V2.
//
// The host application captures system audio, runs an FFT and streams 30
// log-spaced band levels to the keyboard as 32-byte raw HID reports (VIA
// raw HID endpoint, consumed via the multimode via_command_user() hook).
// This module keeps the band envelope (fast attack / speed-scaled release),
// per-column peak values and the overall level, and renders three effect
// styles:
//
//   MV_SPECTRUM : bottom-up spectrum bars, rainbow hue per column,
//                 peak-hold dots with gravity.
//   MV_CENTER   : mirrored horizontal bars growing outward from the
//                 center column (low frequencies at the center).
//   MV_PULSE    : loudness-driven brightness wash with slow hue drift
//                 and a white flash on beats.
//
// When no packet arrives for MV_IDLE_TIMEOUT_MS the level envelope decays
// and the effect renders a dim, slowly hue-rotating idle state.

#include QMK_KEYBOARD_H
#include "music_viz.h"

#ifdef RGB_MATRIX_ENABLE

#define MV_STYLE_SPECTRUM 0
#define MV_STYLE_CENTER   1
#define MV_STYLE_PULSE    2

#define MV_COLUMN_COUNT 15

// Envelope fall speed in level units per second, at RGB speed 0.
// Actual fall speed = MV_RELEASE_BASE + rgb_matrix_get_speed().
#define MV_RELEASE_BASE 130
#define MV_IDLE_TIMEOUT_MS 500
#define MV_BEAT_DELTA 55
#define MV_FLASH_FALL 900  // flash units per second

// Idle glow floors per style (applied once the stream is stale).
#define MV_IDLE_FLOOR_SPECTRUM 30
#define MV_IDLE_FLOOR_CENTER 36
#define MV_IDLE_FLOOR_PULSE 28

static uint8_t mv_raw[MV_BAND_COUNT];
static uint8_t mv_level[MV_BAND_COUNT];
static uint8_t mv_col_level[MV_COLUMN_COUNT];
static uint8_t mv_col_peak[MV_COLUMN_COUNT];

static uint32_t mv_last_packet;
static uint32_t mv_last_tick;
static uint8_t  mv_overall;
static uint8_t  mv_prev_overall;
static uint8_t  mv_flash;

static bool    mv_geom_ready;
static uint8_t mv_led_col[RGB_MATRIX_LED_COUNT];
static uint8_t mv_led_row[RGB_MATRIX_LED_COUNT];

// Row lighting thresholds for bottom-up bars: row 0 is the top row,
// row 4 the bottom (spacebar) row.
static const uint8_t mv_row_thresh[5] = {230, 179, 128, 77, 26};

static void mv_init_geometry(void) {
    for (uint8_t i = 0; i < RGB_MATRIX_LED_COUNT; i++) {
        uint8_t x   = g_led_config.point[i].x;
        uint8_t y   = g_led_config.point[i].y;
        uint8_t col = x / 15;
        uint8_t row = y / 16;
        if (col >= MV_COLUMN_COUNT) col = MV_COLUMN_COUNT - 1;
        if (row > 4) row = 4;
        mv_led_col[i] = col;
        mv_led_row[i] = row;
    }
    mv_geom_ready = true;
}

static void mv_reset_state(void) {
    for (uint8_t i = 0; i < MV_BAND_COUNT; i++) {
        mv_raw[i]   = 0;
        mv_level[i] = 0;
    }
    for (uint8_t c = 0; c < MV_COLUMN_COUNT; c++) {
        mv_col_level[c] = 0;
        mv_col_peak[c]  = 0;
    }
    mv_overall      = 0;
    mv_prev_overall = 0;
    mv_flash        = 0;
    mv_last_packet  = 0;
    mv_last_tick    = timer_read32();
}

// Top-most lit row for a given level, -1 when nothing lights up.
static inline int8_t mv_top_row(uint8_t level) {
    for (uint8_t r = 0; r < 5; r++) {
        if (level >= mv_row_thresh[r]) return (int8_t)r;
    }
    return -1;
}

// Advance the envelope. Called once per RGB frame from music_viz_render().
static void mv_tick(void) {
    uint32_t now = timer_read32();
    uint32_t dt  = timer_elapsed32(mv_last_tick);
    mv_last_tick = now;
    if (dt == 0) {
        return;
    }
    if (dt > 250) {
        dt = 250;
    }

    bool stale = (mv_last_packet == 0) || (timer_elapsed32(mv_last_packet) > MV_IDLE_TIMEOUT_MS);

    uint16_t release = MV_RELEASE_BASE + rgb_matrix_get_speed();
    uint16_t peakfall = (release >> 1) + 40;
    uint16_t drop     = (release * dt) / 1000;
    uint16_t pdrop    = (peakfall * dt) / 1000;
    if (drop == 0) drop = 1;
    if (pdrop == 0) pdrop = 1;

    uint16_t maxlvl = 0;
    for (uint8_t i = 0; i < MV_BAND_COUNT; i++) {
        uint8_t target = stale ? 0 : mv_raw[i];
        // Fast attack, time-based release.
        if (target >= mv_level[i]) {
            mv_level[i] = target;
        } else {
            mv_level[i] = (mv_level[i] > drop) ? mv_level[i] - drop : 0;
        }
        if (mv_level[i] > maxlvl) {
            maxlvl = mv_level[i];
        }
    }

    for (uint8_t c = 0; c < MV_COLUMN_COUNT; c++) {
        uint8_t lvl = mv_level[2 * c] > mv_level[2 * c + 1] ? mv_level[2 * c] : mv_level[2 * c + 1];
        mv_col_level[c] = lvl;
        if (lvl >= mv_col_peak[c]) {
            mv_col_peak[c] = lvl;
        } else {
            mv_col_peak[c] = (mv_col_peak[c] > pdrop) ? mv_col_peak[c] - pdrop : 0;
        }
    }

    uint8_t ov = (uint8_t)maxlvl;
    if (ov >= mv_overall) {
        mv_overall = ov;
    } else {
        uint16_t ovdrop = (drop >> 1) + 1;
        mv_overall      = (mv_overall > ovdrop) ? mv_overall - ovdrop : 0;
    }

    if ((mv_overall > mv_prev_overall) && ((uint8_t)(mv_overall - mv_prev_overall) > MV_BEAT_DELTA)) {
        mv_flash = 255;
    }
    mv_prev_overall = mv_overall;
    if (mv_flash > 0) {
        uint16_t fdrop = (MV_FLASH_FALL * dt) / 1000 + 1;
        mv_flash       = (mv_flash > fdrop) ? mv_flash - fdrop : 0;
    }
}

static void mv_render_spectrum(uint8_t led_min, uint8_t led_max, bool stale) {
    uint8_t hue0 = rgb_matrix_config.hsv.h + (stale ? (uint8_t)(timer_read32() >> 7) : 0);
    uint8_t sat  = rgb_matrix_config.hsv.s;
    uint8_t val  = rgb_matrix_config.hsv.v;

    for (uint8_t i = led_min; i < led_max; i++) {
        uint8_t col  = mv_led_col[i];
        uint8_t row  = mv_led_row[i];
        uint8_t lvl  = mv_col_level[col];
        uint8_t peak = mv_col_peak[col];
        if (stale && lvl < MV_IDLE_FLOOR_SPECTRUM) {
            lvl = MV_IDLE_FLOOR_SPECTRUM;
        }

        int8_t top = mv_top_row(lvl);
        if (top >= 0 && row >= (uint8_t)top) {
            RGB c = hsv_to_rgb((HSV){hue0 + col * 6, sat, val});
            rgb_matrix_set_color(i, c.r, c.g, c.b);
        } else {
            int8_t ptop = mv_top_row(peak);
            if (ptop >= 0 && row == (uint8_t)ptop) {
                // Peak-hold dot.
                rgb_matrix_set_color(i, val, val, val);
            } else {
                rgb_matrix_set_color(i, 0, 0, 0);
            }
        }
    }
}

static void mv_render_center(uint8_t led_min, uint8_t led_max, bool stale) {
    uint8_t hue0 = rgb_matrix_config.hsv.h + (stale ? (uint8_t)(timer_read32() >> 7) : 0);
    uint8_t sat  = rgb_matrix_config.hsv.s;
    uint8_t val  = rgb_matrix_config.hsv.v;

    for (uint8_t i = led_min; i < led_max; i++) {
        uint8_t col  = mv_led_col[i];
        uint8_t row  = mv_led_row[i];
        uint8_t dist = (col <= 7) ? (7 - col) : (col - 7);  // 0..7 from the center column
        uint8_t lvl  = mv_col_level[7 + dist];              // outward = higher frequency bands
        if (stale && lvl < MV_IDLE_FLOOR_CENTER) {
            lvl = MV_IDLE_FLOOR_CENTER;
        }
        uint8_t reach = (uint8_t)(((uint16_t)lvl * 8) / 256);  // 0..7 columns outward

        if (dist <= reach) {
            // Brighter towards the bottom (spacebar) row.
            uint8_t v = (uint8_t)(((uint16_t)val * (row + 1)) / 5);
            RGB     c = hsv_to_rgb((HSV){hue0 + dist * 8, sat, v});
            rgb_matrix_set_color(i, c.r, c.g, c.b);
        } else {
            rgb_matrix_set_color(i, 0, 0, 0);
        }
    }
}

static void mv_render_pulse(uint8_t led_min, uint8_t led_max, bool stale) {
    uint32_t t     = timer_read32();
    uint8_t  spd   = rgb_matrix_get_speed();
    uint8_t  drift = (uint8_t)((t * (16 + (spd >> 4))) >> 10);
    uint8_t  base  = rgb_matrix_config.hsv.h + drift;
    uint8_t  sat   = rgb_matrix_config.hsv.s;
    uint8_t  eff   = mv_overall;
    if (stale && eff < MV_IDLE_FLOOR_PULSE) {
        eff = MV_IDLE_FLOOR_PULSE;
    }

    uint16_t bright = ((uint16_t)rgb_matrix_config.hsv.v * eff) / 255 + mv_flash;
    if (bright > 255) bright = 255;

    for (uint8_t i = led_min; i < led_max; i++) {
        uint8_t hue = base + mv_led_col[i] * 5 + mv_led_row[i] * 2;
        RGB     c   = hsv_to_rgb((HSV){hue, sat, (uint8_t)bright});
        rgb_matrix_set_color(i, c.r, c.g, c.b);
    }
}

static void mv_render(uint8_t style, uint8_t led_min, uint8_t led_max) {
    if (!mv_geom_ready) {
        mv_init_geometry();
    }
    // Physics once per frame (led_min == 0 only on the first slice).
    if (led_min == 0) {
        mv_tick();
    }

    bool stale = (mv_last_packet == 0) || (timer_elapsed32(mv_last_packet) > MV_IDLE_TIMEOUT_MS);
    switch (style) {
        case MV_STYLE_SPECTRUM:
            mv_render_spectrum(led_min, led_max, stale);
            break;
        case MV_STYLE_CENTER:
            mv_render_center(led_min, led_max, stale);
            break;
        default:
            mv_render_pulse(led_min, led_max, stale);
            break;
    }
}

void music_viz_render_spectrum(uint8_t led_min, uint8_t led_max) {
    mv_render(MV_STYLE_SPECTRUM, led_min, led_max);
}

void music_viz_render_center(uint8_t led_min, uint8_t led_max) {
    mv_render(MV_STYLE_CENTER, led_min, led_max);
}

void music_viz_render_pulse(uint8_t led_min, uint8_t led_max) {
    mv_render(MV_STYLE_PULSE, led_min, led_max);
}

bool music_viz_process_hid(uint8_t *data, uint8_t length) {
    if (length < 2 || data[0] != MV_HID_MAGIC || (data[1] & 0x0F) != MV_HID_VERSION) {
        return false;
    }
    uint8_t n = length - 2;
    if (n > MV_BAND_COUNT) {
        n = MV_BAND_COUNT;
    }
    for (uint8_t i = 0; i < MV_BAND_COUNT; i++) {
        mv_raw[i] = (i < n) ? data[2 + i] : 0;
    }
    mv_last_packet = timer_read32();
    return true;
}

void music_viz_next_mode(void) {
#ifdef ENABLE_RGB_MATRIX_MV_SPECTRUM
    uint8_t first = RGB_MATRIX_CUSTOM_MV_SPECTRUM;
    uint8_t last  = first;
#    ifdef ENABLE_RGB_MATRIX_MV_PULSE
    last = RGB_MATRIX_CUSTOM_MV_PULSE;
#    endif
    uint8_t mode = rgb_matrix_get_mode();
    uint8_t next = (mode < first || mode >= last) ? first : mode + 1;

    mv_reset_state();
    rgb_matrix_mode(next);
#endif
}

#ifdef VIA_ENABLE
// Called by the multimode framework's via_command_user() (via the
// via_command_user_kb hook) for every raw HID report. Consume only our
// magic packets; everything else flows on to VIA.
bool via_command_user_kb(uint8_t *data, uint8_t length) {
    return music_viz_process_hid(data, length);
}
#endif

#endif  // RGB_MATRIX_ENABLE
