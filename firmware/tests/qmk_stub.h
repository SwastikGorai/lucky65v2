#pragma once
#include <stdint.h>
#include <stdbool.h>
#define RGB_MATRIX_ENABLE
#define VIA_ENABLE
#define RGB_MATRIX_MAXIMUM_BRIGHTNESS 200
#define HSV_RED 0,255,255
#define HSV_YELLOW 43,255,255
#define HSV_GREEN 85,255,255
#define HSV_CYAN 128,255,255
#define HSV_BLUE 170,255,255
#define HSV_PINK 234,128,255
#define HSV_WHITE 0,0,255
#define RGB_MATRIX_LED_COUNT 67
#define RGB_MATRIX_CUSTOM_MV_BREATHING 45
#define RGB_MATRIX_CUSTOM_MV_BAR 46
typedef struct { uint8_t h, s, v; } HSV;
typedef struct { uint8_t r, g, b; } RGB;
static struct { HSV hsv; uint8_t mode; } rgb_matrix_config;
static struct { struct { uint8_t x, y; } point[67]; } g_led_config;
static RGB colors[67];
static uint32_t now;
static unsigned saves, mode_changes;
static uint32_t timer_read32(void) { return now; }
static uint8_t rgb_matrix_get_mode(void) { return rgb_matrix_config.mode; }
static void rgb_matrix_mode(uint8_t mode) { rgb_matrix_config.mode = mode; mode_changes++; }
static void eeconfig_update_rgb_matrix(void) { saves++; }
static bool enabled;
static void rgb_matrix_enable_noeeprom(void) { enabled = true; }
static bool rgb_matrix_is_enabled(void) { return enabled; }
static void rgb_matrix_mode_noeeprom(uint8_t mode) { rgb_matrix_config.mode = mode; }
static void rgb_matrix_sethsv_noeeprom(uint8_t h, uint8_t s, uint8_t v) { rgb_matrix_config.hsv = (HSV){h,s,v}; }
static void rgb_matrix_sethsv(uint8_t h, uint8_t s, uint8_t v) { rgb_matrix_sethsv_noeeprom(h,s,v); saves++; }
// Expose HSV inputs to assert selected color and brightness independently.
static RGB hsv_to_rgb(HSV hsv) { return (RGB){hsv.h, hsv.s, hsv.v}; }
static void rgb_matrix_set_color(uint8_t i, uint8_t r, uint8_t g, uint8_t b) { colors[i] = (RGB){r,g,b}; }
typedef struct { struct { bool pressed; struct { uint8_t row, col; } key; } event; } keyrecord_t;
enum { _LB, _LF, _LS, _LM, _LMF, _LMS, RGB_MOD, KC_RCTL };
#define MOD_BIT(k) (1U << (k))
static uint8_t mods, active_layer;
static uint8_t get_mods(void) { return mods; }
static bool layer_state_is(uint8_t layer) { return active_layer == layer; }
