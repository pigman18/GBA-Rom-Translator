/*
 * TODO(未验�?: 未挂 main.asm�? * 旧问题：GetStringWidth+0x0C �?BL 超范围；F9 测宽未冒烟�? * 对应 pokeruby: GetStringWidth (src/text.c)
 * 逻辑�?GetStringWidthChinese.s 移植，启用前需单独薄壳对齐原寄存器约定�? */
#include "game.h"

int GetStringWidth_Chinese(TextPrinter *win, const uint8_t *s,
                           uint16_t *index, uint8_t *width)
{
    uint16_t i = *index;
    uint8_t ch = s[i];
    if (ch != CHS_ESCAPE)
        return 0;

    uint8_t op = s[i + 1];
    uint8_t font = win_u8(win, WIN_FONTNUM);
    int glyph_px = (font == FONT_NORMAL_UNSHADOWED || font == FONT_NORMAL_SHADOWED)
                       ? 16
                       : 10;

    if (op == 0) {
        *width = (uint8_t)((*width + glyph_px) & 0xFF);
        *index = (uint16_t)(i + 4);
        return 1;
    }

    /* F9 XX hi lo �?短语：按字数 × 单字�?*/
    uint16_t code = (uint16_t)((s[i + 2] << 8) | s[i + 3]);
    const uint16_t *offsets = (const uint16_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint8_t count = table[offsets[code]];
    int add = (font == FONT_NORMAL_UNSHADOWED || font == FONT_NORMAL_SHADOWED)
                  ? (count * 16)
                  : (count * 8 + count * 2); /* �?asm: count*8 + count*2 */
    *width = (uint8_t)((*width + add) & 0xFF);
    *index = (uint16_t)(i + 4);
    return 1;
}
