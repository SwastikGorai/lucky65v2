// Copyright 2026 The Lucky65 V2 Music Visualizer mod authors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Custom RGB matrix effects for the music visualizer (RGB_MATRIX_CUSTOM_KB).
// This file is expanded by rgb_matrix internals (enum list, implementation
// pass and switch pass), so it must not include headers at top level.

#ifdef ENABLE_RGB_MATRIX_MV_SPECTRUM
RGB_MATRIX_EFFECT(MV_SPECTRUM)
#    ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS

bool MV_SPECTRUM(effect_params_t *params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);

    extern void music_viz_render_spectrum(uint8_t led_min, uint8_t led_max);
    music_viz_render_spectrum(led_min, led_max);

    return rgb_matrix_check_finished_leds(led_max);
}

#    endif  // RGB_MATRIX_CUSTOM_EFFECT_IMPLS
#endif

#ifdef ENABLE_RGB_MATRIX_MV_CENTER
RGB_MATRIX_EFFECT(MV_CENTER)
#    ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS

bool MV_CENTER(effect_params_t *params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);

    extern void music_viz_render_center(uint8_t led_min, uint8_t led_max);
    music_viz_render_center(led_min, led_max);

    return rgb_matrix_check_finished_leds(led_max);
}

#    endif  // RGB_MATRIX_CUSTOM_EFFECT_IMPLS
#endif

#ifdef ENABLE_RGB_MATRIX_MV_PULSE
RGB_MATRIX_EFFECT(MV_PULSE)
#    ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS

bool MV_PULSE(effect_params_t *params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);

    extern void music_viz_render_pulse(uint8_t led_min, uint8_t led_max);
    music_viz_render_pulse(led_min, led_max);

    return rgb_matrix_check_finished_leds(led_max);
}

#    endif  // RGB_MATRIX_CUSTOM_EFFECT_IMPLS
#endif
