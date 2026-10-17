#include <assert.h>
#include <stdio.h>
#include <string.h>
#define QMK_KEYBOARD_H "qmk_stub.h"
#include "../keyboards/lucky65v2/music_viz.c"
#include "shortcut.h"

static void reset(void) {
    now = mv_level = mv_last_packet = mv_last_tick = 0;
    mv_raw = 0; mv_received = false;
    rgb_matrix_config.hsv = (HSV){17, 219, 200};
}
static void packet(uint8_t level) {
    uint8_t data[32] = {MV_HID_MAGIC, MV_HID_VERSION};
    data[31] = level;
    assert(via_command_user_kb(data, sizeof(data)));
}
static void advance(uint32_t ms, uint8_t level) {
    now += ms; packet(level); music_viz_render_breathing(0, 67);
}
static uint32_t envelope(uint32_t interval, bool release) {
    reset();
    if (release) mv_level = MV_FULL;
    for (unsigned t = 0; t < 240; t += interval) advance(interval, release ? 0 : 128);
    return mv_level;
}
int main(void) {
    for (unsigned i=0; i<67; i++) g_led_config.point[i].y = (i % 5) * 16;
    reset();
    packet(128); // A packet at timer zero is valid.
    uint32_t target = (128UL * MV_FULL) / 235;
    for (unsigned i=0; i<200; i++) {
        uint32_t previous = mv_level;
        advance(16, 128);
        assert(mv_level >= previous && mv_level <= target);
    }
    assert(mv_level == target);
    for (unsigned i=0; i<100; i++) { advance(16,128); assert(mv_level == target); }
    for (unsigned i=0; i<300; i++) {
        uint32_t previous = mv_level;
        advance(16, 0);
        assert(mv_level <= previous);
    }
    assert(mv_level == 0);
    for (unsigned release=0; release<2; release++) {
        assert(envelope(1, release) == envelope(8, release));
        assert(envelope(8, release) == envelope(16, release));
        assert(envelope(16, release) == envelope(40, release));
    }
    reset(); advance(40,235);
    assert(mv_level > MV_FULL * 62 / 100 && mv_level < MV_FULL * 65 / 100);
    mv_level = MV_FULL; advance(180,0);
    assert(mv_level > MV_FULL * 35 / 100 && mv_level < MV_FULL * 38 / 100);

    reset(); advance(16,128);
    uint32_t snapshot = mv_level;
    now += 10;
    music_viz_render_breathing(20,67);
    assert(mv_level == snapshot); // Later slices must not tick.
    for (unsigned i=1;i<67;i++) assert(memcmp(&colors[0], &colors[i], sizeof(RGB)) == 0);
    assert(colors[0].r == 17 && colors[0].g == 219);

    for (unsigned level=0; level<=255; level++) {
        mv_level = (uint32_t)level << 16; mv_last_tick = now;
        music_viz_render_bar(0,67);
        for (unsigned i=5;i<67;i++) assert(colors[i].b == colors[i%5].b);
        for (unsigned row=0;row<4;row++) assert(colors[row].b <= colors[row+1].b);
        if (!level) assert(colors[4].b == 0);
        if (level==255) assert(colors[0].b == 200);
    }
    mv_level = MV_FULL/10; music_viz_render_bar(0,67);
    assert(colors[4].b >= 99 && colors[4].b <= 100 && colors[3].b == 0);
    rgb_matrix_config.hsv.v = 0;
    music_viz_render_bar(0,67); for (unsigned i=0;i<67;i++) assert(colors[i].b == 0);
    music_viz_render_breathing(0,67); assert(colors[0].b == 0);
    reset(); advance(2000,235); assert(mv_level == MV_FULL);
    advance(16,255); assert(mv_level == MV_FULL);
    now += 501; music_viz_render_breathing(0,67); assert(mv_level < MV_FULL);
    now += 4000; music_viz_render_breathing(0,67); assert(mv_level == 0);
    reset(); now = UINT32_MAX-20; mv_last_tick = now; packet(128);
    now += 40; music_viz_render_breathing(0,67); assert(mv_level > 0);
    uint8_t bad[] = {0, 1, 255}; assert(!music_viz_process_hid(bad,3));
    assert(!music_viz_process_hid(bad,1));
    uint8_t probe[] = {MV_HID_MAGIC, 0x81, 38};
    assert(music_viz_process_hid(probe,3)); assert(music_viz_probe_led() == 38);
    probe[2] = 255; assert(music_viz_process_hid(probe,3)); assert(music_viz_probe_led() == 255);
    rgb_matrix_config.mode = 47; keyboard_post_init_user();
    assert(rgb_matrix_config.mode == RGB_MATRIX_CUSTOM_MV_BREATHING && saves == 1);
    rgb_matrix_config.mode = 13; keyboard_post_init_user(); assert(saves == 1);
    music_viz_next_mode(); assert(rgb_matrix_config.mode == RGB_MATRIX_CUSTOM_MV_BREATHING);
    music_viz_next_mode(); assert(rgb_matrix_config.mode == RGB_MATRIX_CUSTOM_MV_BAR);
    music_viz_next_mode(); assert(rgb_matrix_config.mode == RGB_MATRIX_CUSTOM_MV_BREATHING);

    for (unsigned layer=0;layer<6;layer++) {
        active_layer=layer; mods=MOD_BIT(KC_RCTL);
        keyrecord_t key = {.event={.pressed=true,.key={1,13}}};
        unsigned before=mode_changes;
        bool fn=layer!=_LB && layer!=_LM;
        assert(im_process_record_user(RGB_MOD,&key) == !fn);
        assert(mode_changes == before + fn);
        if (fn) {
            assert(!im_process_record_user(RGB_MOD,&key)); assert(mode_changes == before+1);
            mods=0; active_layer=_LB; key.event.pressed=false;
            assert(!im_process_record_user(0,&key)); // Release after modifiers/layer change.
        }
        active_layer=layer; mods=0; key.event.pressed=true;
        assert(im_process_record_user(RGB_MOD,&key));
        mods=1; // Left Ctrl must not activate the music chord.
        assert(im_process_record_user(RGB_MOD,&key));
        key.event.key.row=4; key.event.key.col=8;
        assert(im_process_record_user(KC_RCTL,&key));
        key.event.pressed=false;
        assert(im_process_record_user(KC_RCTL,&key));
    }
    rgb_matrix_config.mode = RGB_MATRIX_CUSTOM_MV_BREATHING;
    mv_set_color(6, false);
    assert(music_viz_cycle_color(false) && mv_color() == 7);
    assert(music_viz_cycle_color(false) && mv_color() == 0);
    assert(music_viz_cycle_color(true) && mv_color() == 7);
    now = 6000; packet(235); music_viz_render_breathing(0,20);
    now += 100; music_viz_render_breathing(20,67);
    assert(colors[0].r == 128 && colors[20].r == 128);
    now += 5000; music_viz_render_breathing(0,67); assert(colors[0].b == 0);
    unsigned saved = saves;
    uint8_t control[32] = {MV_CONTROL_MAGIC,1,1,2};
    assert(music_viz_process_hid(control,32));
    assert(reply[3] == 2 && reply[4] == 7 && reply[6] == 1);
    control[2] = 3; control[3] = 100; music_viz_process_hid(control,32);
    assert(reply[5] == 100 && saves == saved);
    unsigned sent = replies;
    control[3] = 201; music_viz_process_hid(control,32);
    assert(replies == sent && rgb_matrix_config.hsv.v == 100);
    control[2] = 2; control[3] = 8; music_viz_process_hid(control,32);
    assert(replies == sent);
    control[3] = 4; music_viz_process_hid(control,31); assert(replies == sent);
    music_viz_process_hid(control,32); assert(reply[4] == 4 && !mv_drift);
    puts("PASS: smoothing, rendering, HID, timeout, shortcuts, drift, live controls");
}
