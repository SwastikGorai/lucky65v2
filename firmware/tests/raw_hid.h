#pragma once
static uint8_t reply[32];
static unsigned replies;
static void raw_hid_send(uint8_t *data, uint8_t length) {
    assert(length == 32);
    memcpy(reply, data, length);
    replies++;
}
