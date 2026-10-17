// SPDX-License-Identifier: GPL-2.0-or-later
// Expanded for enums and implementations; no headers at top level.
#ifdef ENABLE_RGB_MATRIX_MV_BREATHING
RGB_MATRIX_EFFECT(MV_BREATHING)
#    ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS
bool MV_BREATHING(effect_params_t *params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    extern void music_viz_render_breathing(uint8_t led_min, uint8_t led_max);
    music_viz_render_breathing(led_min, led_max);
    return rgb_matrix_check_finished_leds(led_max);
}
#    endif
#endif

#ifdef ENABLE_RGB_MATRIX_MV_BAR
RGB_MATRIX_EFFECT(MV_BAR)
#    ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS
bool MV_BAR(effect_params_t *params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    extern void music_viz_render_bar(uint8_t led_min, uint8_t led_max);
    music_viz_render_bar(led_min, led_max);
    return rgb_matrix_check_finished_leds(led_max);
}
#    endif
#endif
