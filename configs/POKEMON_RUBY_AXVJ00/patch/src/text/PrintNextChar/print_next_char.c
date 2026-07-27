/* ?? pokeruby PrintNextChar � F9 ????????? */
#include "game.h"

/** Was: force WIN_TILE_OFFSET from ChineseTileState.next_abs (menu floor /
 * sticky). That hijack mapped BG tiles into dialogue (green squares).
 * Linear dest now trusts the window's TILE_OFFSET only — see draw_glyph.c.
 */
static void ensure_linear_tile_bump(TextPrinter *win)
{
    (void)win;
}

static int lead_trail_ok(uint8_t lead, uint8_t trail)
{
    if (lead >= 0xFA || trail >= 0xFA)
        return 0;
    if (lead < 0x01 || lead > 0x1E)
        return 0;
    if (lead == 0x06 || lead == 0x1B)
        return 0;
    return 1;
}

static uint16_t pack_glyph_index(uint8_t lead, uint8_t trail)
{
    uint32_t idx = lead;
    if (idx >= 6) {
        if (idx >= 0x1B)
            idx -= 1;
        idx -= 1;
    }
    idx -= 1;
    return (uint16_t)((idx << 8) | trail);
}

static const uint8_t *glyph_ptr(uint16_t index)
{
    /* 128B / glyph: 16x16 4bpp slot (TL,BL,TR,BR) — Gen3 hardware container. */
    return (const uint8_t *)(ADDR_FONT_CHS_NORMAL + ((uint32_t)index << 7));
}

static void draw_phrase(TextPrinter *win, uint16_t code)
{
    const uint16_t *offsets = (const uint16_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint16_t off = offsets[code];
    const uint8_t *entry = table + off;
    uint8_t count = entry[0];
    const uint16_t *indices = (const uint16_t *)(entry + 2);

    for (uint8_t i = 0; i < count; i++)
        DrawGlyph_Chinese(win, glyph_ptr(indices[i]));
}

/**
 * PrintNextChar ???????? / ?? + sticky?
 * F9 7F ?? write.op??? +4 ???
 */
int PrintNextChar_C(TextPrinter *win, uint32_t cur_char)
{
    ensure_linear_tile_bump(win);

    if (cur_char != CHS_ESCAPE)
        return 0;

    const uint8_t *text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    uint16_t index = win_u16(win, WIN_TEXT_INDEX);
    const uint8_t *p = text + index;
    uint8_t op = p[0];

    if (op == 0) {
        if (index == 1)
            chinese_tile_state()->write_op = 0;
        uint8_t lead = p[1];
        uint8_t trail = p[2];
        if (!lead_trail_ok(lead, trail))
            return 0;

        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
        uint16_t gidx = pack_glyph_index(lead, trail);
        if (gidx >= CHS_FONT_GLYPH_MAX)
            return 1;
        DrawGlyph_Chinese(win, glyph_ptr(gidx));
        return 1;
    }

    volatile struct ChineseTileState *st = chinese_tile_state();
    if (op == CHS_PHRASE_DEFAULT) {
        st->write_op = 0;
    } else {
        st->write_op = op;
        if (op < 3)
            st->next_abs = 0;
    }

    uint16_t code = (uint16_t)((p[1] << 8) | p[2]);
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
    draw_phrase(win, code);
    return 1;
}
