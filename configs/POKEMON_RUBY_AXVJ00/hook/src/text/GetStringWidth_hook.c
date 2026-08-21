/* GetStringWidth_hook — pokeRS GetStringWidthChinese + F900/F980 widths. */
#include "game.h"

/* Walk PhraseTable PCS stream: F9 00 → glyph_px; FA..FE skip; stop at FF. */
static int phrase_stream_width(const uint8_t *stream, int glyph_px)
{
    int add = 0;
    unsigned i = 0;

    while (stream[i] != 0xFF) {
        uint8_t c = stream[i];
        if (c == CHS_ESCAPE) {
            if (stream[i + 1] == 0) {
                add += glyph_px;
                i += 4; /* F9 00 lead trail */
            } else {
                /* Nested phrase ref inside stream — treat as 0 (should not occur). */
                i += 4;
            }
            continue;
        }
        if (c >= 0xFA) {
            i++;
            continue;
        }
        add += 8;
        i++;
    }
    return add;
}

static int glyph_px_for_win(const TextPrinter *win)
{
    uint8_t font = win_u8(win, WIN_FONTNUM_REAL);
    if (font == FONT_NORMAL_UNSHADOWED || font == FONT_NORMAL_SHADOWED)
        return CHS_GLYPH_ADVANCE_PX;
    return 10;
}

/* Pixel width of one F9 sequence at s[i]; advances *index. */
static int f9_width_at(const uint8_t *s, uint16_t *index, int glyph_px)
{
    uint16_t i = *index;
    uint8_t op = s[i + 1];

    if (op == 0) {
        *index = (uint16_t)(i + 4);
        return glyph_px;
    }

    {
        uint16_t code = (uint16_t)((s[i + 2] << 8) | s[i + 3]);
        const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
        const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
        const uint8_t *stream = table + offsets[code];
        *index = (uint16_t)(i + 4);
        return phrase_stream_width(stream, glyph_px);
    }
}

static int string_width_px(const uint8_t *s, int glyph_px)
{
    int width = 0;
    uint16_t i = 0;

    while (s[i] != 0xFF) {
        uint8_t c = s[i];
        if (c == CHS_ESCAPE) {
            width += f9_width_at(s, &i, glyph_px);
            continue;
        }
        if (c >= 0xFA) {
            i++;
            continue;
        }
        width += 8;
        i++;
    }
    return width;
}

int GetStringWidth_Chinese(TextPrinter *win, const uint8_t *s,
                           uint16_t *index, uint8_t *width)
{
    uint16_t i = *index;
    if (s[i] != CHS_ESCAPE)
        return 0;

    {
        int add = f9_width_at(s, index, glyph_px_for_win(win));
        *width = (uint8_t)((*width + add) & 0xFF);
        return 1;
    }
}

/*
 * Full (win, str) → pixel width (draw-matched advances).
 */
uint8_t GetStringWidthChinese_Full(TextPrinter *win, const uint8_t *s)
{
    return (uint8_t)(string_width_px(s, glyph_px_for_win(win)) & 0xFF);
}
