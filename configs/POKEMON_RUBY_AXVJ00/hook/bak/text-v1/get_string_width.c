/* F9-aware string width: Hanzi advance matches draw (CHS_GLYPH_ADVANCE_PX). */
#include "game.h"

int GetStringWidth_Chinese(TextPrinter *win, const uint8_t *s,
                           uint16_t *index, uint8_t *width)
{
    uint16_t i = *index;
    uint8_t ch = s[i];
    if (ch != CHS_ESCAPE)
        return 0;

    {
        uint8_t op = s[i + 1];
        uint8_t font = win_u8(win, WIN_FONTNUM_REAL);
        int glyph_px = (font == FONT_NORMAL_UNSHADOWED || font == FONT_NORMAL_SHADOWED)
                           ? CHS_GLYPH_ADVANCE_PX
                           : 10;

        if (op == 0) {
            *width = (uint8_t)((*width + glyph_px) & 0xFF);
            *index = (uint16_t)(i + 4);
            return 1;
        }

        /* F9 XX hi lo — phrase: walk encoded byte stream for width */
        {
            uint16_t code = (uint16_t)((s[i + 2] << 8) | s[i + 3]);
            const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
            const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
            const uint8_t *p = table + offsets[code];
            int add = 0, max_add = 0;
            for (;;) {
                uint8_t c = *p++;
                if (c == CHS_ESCAPE) {
                    if (p[0] == CHS_PHRASE_END)
                        break;
                    if (p[0] == 0) {   /* F9 00 ll tt */
                        add += glyph_px;
                        p += 3;
                    }
                    continue;
                }
                if (c == 0xFE) {       /* newline: per-line width, keep max */
                    if (add > max_add) max_add = add;
                    add = 0;
                    continue;
                }
                if (c >= 0xFA)         /* other controls: no advance */
                    continue;
                add += 8;
            }
            if (add > max_add) max_add = add;
            *width = (uint8_t)((*width + max_add) & 0xFF);
            *index = (uint16_t)(i + 4);
            return 1;
        }
    }
}

/*
 * Full (win, str) → width for thin-shell GetStringWidth replace.
 *
 * 与 drawGlyph12 保持一致的 advance：F9 序列走
 * CHS_GLYPH_ADVANCE_PX（12px），JP 原版半角字符走 8px。
 * 右半字仅4px，不额外推进。计算不包含右边距残余。
 */
uint8_t GetStringWidthChinese_Full(TextPrinter *win, const uint8_t *s)
{
    uint8_t width = 0;
    uint16_t i = 0;

    while (s[i] != 0xFF) {
        uint8_t c = s[i];
        if (c == CHS_ESCAPE) {
            uint16_t idx = i;
            if (GetStringWidth_Chinese(win, s, &idx, &width)) {
                i = idx;
                continue;
            }
        }
        /* JP fixed cell 8; Sym punct also left-8 (draw_sym_punct, no 12px spill). */
        if (c >= 0xFA) {
            i++;
            continue;
        }
        width = (uint8_t)((width + 8) & 0xFF);
        i++;
    }
    return width;
}
