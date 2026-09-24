#ifndef FAKE_TR_H
#define FAKE_TR_H
#include <stdint.h>
struct GlyphTileInfo {
    uint8_t textMode;
    uint8_t startPixel;
    uint8_t width;
    uint8_t *src;
    uint32_t *dest;
    uint32_t *colors;
};
struct GlyphBuffer {
    uint32_t pixelRows[16];
    uint32_t background;
    uint32_t colors[16];
};
#define TEXT_MODE_UNKNOWN2 2u
#endif
