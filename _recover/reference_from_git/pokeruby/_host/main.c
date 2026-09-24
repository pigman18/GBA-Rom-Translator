#include "text_render.h"
#include <stdio.h>
#include <string.h>
int32_t refpr_draw_tile_shadowed(void *gb, void *info);
int32_t refpr_draw_tile_unshadowed(void *gb, void *info);
static void show(const char *l, const uint8_t *t)
{
    printf("%s\n", l);
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 4; c++) printf("%02X", t[r*4+c]);
        printf("\n");
    }
}
int main(void)
{
    static struct GlyphBuffer gb;
    static struct GlyphTileInfo info;
    uint8_t dest[32], spill[32], temp[32], stage[64];
    memset(&gb, 0, sizeof gb);
    for (int i = 0; i < 16; i++) gb.colors[i] = i;
    gb.colors[0] = 0xD;                      /* nibble0 -> bg terminal */
    memset(dest, 0xA1, 32); memset(spill, 0xB2, 32);
#ifdef NOSWAP
    for (int r = 0; r < 8; r++) {
        temp[r*4+0]=0x12; temp[r*4+1]=0x34; temp[r*4+2]=0x56; temp[r*4+3]=0x78;
    }
#else
    for (int r = 0; r < 8; r++) {            /* pre-swizzled rows */
        temp[r*4+0]=0x21; temp[r*4+1]=0x43; temp[r*4+2]=0x65; temp[r*4+3]=0x87;
    }
#endif
    memcpy(stage, dest, 32); memcpy(stage + 32, spill, 32);
    info.textMode = 0; info.startPixel = 4; info.width = 8;
    info.src = temp; info.dest = (uint32_t *)stage; info.colors = gb.colors;
    refpr_draw_tile_shadowed(&gb, &info);
    memcpy(dest, stage, 32); memcpy(spill, stage + 32, 32);
    show("C dest", dest); show("C spill", spill);
    puts("gb.pixelRows:");
    for (int r = 0; r < 16; r++) printf("   [%02d] %08X\n", r, gb.pixelRows[r]);
    return 0;
}
