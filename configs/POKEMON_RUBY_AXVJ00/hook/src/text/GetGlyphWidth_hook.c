/* GetGlyphWidth_hook — pokeRS GetGlyphWidthChinese algorithm, F9/JP channel.
 *
 * pokeRS (US): lead 0x01–0x1E + trail → return 4 (normal) / 2 (small).
 * AXVJ product uses F9 00 / F9 80; this helper matches draw advances when
 * called with the lead byte already in `glyph` (legacy US ABI) OR when
 * detecting CHS_ESCAPE at current text index (JP).
 *
 * Not hooked in main.asm this pass (no verified JP GetGlyphWidth site).
 */
#include "game.h"

uint8_t GetGlyphWidth_Chinese(TextPrinter *win, uint32_t glyph)
{
    uint8_t font;
    const uint8_t *text;
    uint16_t index;
    uint8_t trail;

    if (!win)
        return 8;

    /* JP F9 escape at current index → full Hanzi advance */
    text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    index = win_u16(win, WIN_TEXT_INDEX);
    if (glyph == CHS_ESCAPE || (text && text[index] == CHS_ESCAPE)) {
        font = win_u8(win, WIN_FONTNUM_REAL);
        if (font == FONT_NORMAL_UNSHADOWED || font == FONT_NORMAL_SHADOWED)
            return (uint8_t)CHS_GLYPH_ADVANCE_PX;
        return 10;
    }

    /* pokeRS lead-range gate (US encoding; unused as inject path) */
    if (glyph < 0x01 || glyph > 0x1E || glyph == 0x06 || glyph == 0x1B)
        return 8;
    if (!text)
        return 8;
    trail = text[index];
    if (trail > 0xF6)
        return 8;

    font = win_u8(win, WIN_FONTNUM_REAL);
    if (font == FONT_NORMAL_UNSHADOWED || font == FONT_NORMAL_SHADOWED)
        return 4; /* pokeRS half-cell; string path uses 12 — see GetStringWidth */
    return 2;
}
