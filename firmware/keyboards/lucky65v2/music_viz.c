// Copyright 2026 The Lucky65 V2 Music Visualizer mod authors
// SPDX-License-Identifier: GPL-2.0-or-later
#include QMK_KEYBOARD_H
#include "music_viz.h"
#ifdef VIA_ENABLE
#    include "raw_hid.h"
#endif

#ifdef RGB_MATRIX_ENABLE
#define MV_IDLE_TIMEOUT_MS 500
#define MV_FULL (255UL << 16)

static uint32_t mv_level; // Q16 retains fractional brightness between frames.
static uint32_t mv_last_packet;
static uint32_t mv_last_tick;
static uint8_t mv_raw;
static uint8_t mv_probe = 0xFF;
static bool mv_received;
static bool mv_drift;
static uint8_t mv_frame_hue;
const uint8_t music_viz_colors[7][3] = {
    {HSV_RED}, {HSV_YELLOW}, {HSV_GREEN}, {HSV_CYAN},
    {HSV_BLUE}, {HSV_PINK}, {HSV_WHITE},
};

static uint8_t mv_mode(void) {
    uint8_t mode = rgb_matrix_get_mode();
    return mode == RGB_MATRIX_CUSTOM_MV_BREATHING ? 1 : mode == RGB_MATRIX_CUSTOM_MV_BAR ? 2 : 0;
}

static uint8_t mv_color(void) {
    if (mv_drift) return 7;
    for (uint8_t i = 0; i < 7; i++) {
        if (rgb_matrix_config.hsv.h == music_viz_colors[i][0] &&
            rgb_matrix_config.hsv.s == music_viz_colors[i][1]) return i;
    }
    return 8; // A custom VIA color, outside the preset cycle.
}

static void mv_set_color(uint8_t color, bool save) {
    mv_drift = color == 7;
    uint8_t preset = mv_drift ? 0 : color;
    if (save) {
        rgb_matrix_sethsv(music_viz_colors[preset][0], music_viz_colors[preset][1], rgb_matrix_config.hsv.v);
    } else {
        rgb_matrix_sethsv_noeeprom(music_viz_colors[preset][0], music_viz_colors[preset][1], rgb_matrix_config.hsv.v);
    }
}

bool music_viz_cycle_color(bool reverse) {
    if (!mv_mode()) return false;
    uint8_t color = mv_color();
    mv_set_color(color > 7 ? 0 : (color + (reverse ? 7 : 1)) % 8, true);
    return true;
}

static void mv_tick(void) {
    uint32_t now = timer_read32();
    uint32_t dt = now - mv_last_tick;
    mv_last_tick = now;
    uint32_t target = mv_received && (now - mv_last_packet <= MV_IDLE_TIMEOUT_MS)
                          ? ((uint32_t)mv_raw * MV_FULL) / 235 : 0;
    if (target > MV_FULL) target = MV_FULL;
    // After a long pause the old envelope is no longer visible.
    if (dt > 4000) dt = 4000;
    // Fixed 1 ms steps give the same attack/release at any RGB frame rate.
    while (dt-- && mv_level != target) {
        if (mv_level < target) {
            mv_level += (target - mv_level + 39) / 40;
        } else {
            mv_level -= (mv_level - target + 179) / 180;
        }
    }
}

static void mv_render(bool bar, uint8_t led_min, uint8_t led_max) {
    if (led_min == 0) {
        mv_tick();
        mv_frame_hue = mv_drift ? (timer_read32() % 12000) * 256 / 12000 : rgb_matrix_config.hsv.h;
    }
    for (uint8_t i = led_min; i < led_max; i++) {
        uint32_t fill = mv_level;
        if (bar) {
            uint8_t row = g_led_config.point[i].y / 16;
            if (row > 4) row = 4;
            uint32_t start = (uint32_t)(4 - row) * MV_FULL;
            fill = mv_level * 5 > start ? mv_level * 5 - start : 0;
            if (fill > MV_FULL) fill = MV_FULL;
        }
        // Divide before multiplying to keep arithmetic within 32 bits.
        uint8_t value = ((fill >> 8) * rgb_matrix_config.hsv.v + (MV_FULL >> 9)) / (MV_FULL >> 8);
        RGB color = hsv_to_rgb((HSV){mv_frame_hue, rgb_matrix_config.hsv.s, value});
        rgb_matrix_set_color(i, color.r, color.g, color.b);
    }
}

void music_viz_render_breathing(uint8_t led_min, uint8_t led_max) {
    mv_render(false, led_min, led_max);
}

void music_viz_render_bar(uint8_t led_min, uint8_t led_max) {
    mv_render(true, led_min, led_max);
}

bool music_viz_process_hid(uint8_t *data, uint8_t length) {
    if (length && data[0] == MV_CONTROL_MAGIC) {
#ifdef VIA_ENABLE
        if (length != 32 || data[1] != MV_HID_VERSION || data[2] > 3) return true;
        switch (data[2]) {
            case 1:
                if (data[3] < 1 || data[3] > 2) return true;
                rgb_matrix_enable_noeeprom();
                rgb_matrix_mode_noeeprom(data[3] == 1 ? RGB_MATRIX_CUSTOM_MV_BREATHING : RGB_MATRIX_CUSTOM_MV_BAR);
                break;
            case 2:
                if (data[3] > 7) return true;
                mv_set_color(data[3], false);
                break;
            case 3:
                if (data[3] > RGB_MATRIX_MAXIMUM_BRIGHTNESS) return true;
                rgb_matrix_sethsv_noeeprom(rgb_matrix_config.hsv.h, rgb_matrix_config.hsv.s, data[3]);
                break;
        }
        uint8_t reply[32] = {MV_CONTROL_MAGIC, MV_HID_VERSION, 0x80, mv_mode(), mv_color(),
                             rgb_matrix_config.hsv.v, rgb_matrix_is_enabled()};
        raw_hid_send(reply, sizeof(reply));
#endif
        return true;
    }
    if (length < 2 || data[0] != MV_HID_MAGIC || (data[1] & 0x0F) != MV_HID_VERSION) return false;
    if (data[1] & 0x80) {
        mv_probe = length >= 3 && data[2] < RGB_MATRIX_LED_COUNT ? data[2] : 0xFF;
        return true;
    }
    mv_raw = 0;
    for (uint8_t i = 2; i < length && i < MV_BAND_COUNT + 2; i++) {
        if (data[i] > mv_raw) mv_raw = data[i];
    }
    mv_last_packet = timer_read32();
    mv_received = true;
    return true;
}

uint8_t music_viz_probe_led(void) {
    return mv_probe;
}

void music_viz_next_mode(void) {
    uint8_t next = rgb_matrix_get_mode() == RGB_MATRIX_CUSTOM_MV_BREATHING
                       ? RGB_MATRIX_CUSTOM_MV_BAR : RGB_MATRIX_CUSTOM_MV_BREATHING;
    rgb_matrix_mode(next);
}

void keyboard_post_init_user(void) {
    mv_last_tick = timer_read32();
    // The removed third music effect may still be saved in EEPROM.
    if (rgb_matrix_get_mode() > RGB_MATRIX_CUSTOM_MV_BAR) {
        rgb_matrix_config.mode = RGB_MATRIX_CUSTOM_MV_BREATHING;
        eeconfig_update_rgb_matrix();
    }
}

#ifdef VIA_ENABLE
bool via_command_user_kb(uint8_t *data, uint8_t length) {
    return music_viz_process_hid(data, length);
}
#endif
#endif
