/* PrintNextChar_hook — F9 优先；普通 JP PCS 也走 DrawGlyphTiles_hook。 */
#include "game.h"

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
    return (const uint8_t *)(ADDR_FONT_CHS_NORMAL + ((uint32_t)index << 7));
}

static int draw_jp_via_chs(TextPrinter *win, uint32_t cur_char);

/*
 * 普通 JP PCS → 同一套 CHS 绘制：
 *   00        → 空白推进 8px
 *   0x36..3E  → Sym
 *   其它可印 → GetGlyphTilePointers + DrawGlyph_Chinese_Adv(8)
 */
static int draw_chs_pcs(TextPrinter *win, uint32_t cur_char)
{
    const uint8_t *src;
    uint8_t tmp[128];
    unsigned i;

    if (cur_char == 0) {
        for (i = 0; i < 128u; i++)
            tmp[i] = 0;
        DrawGlyph_Chinese_Adv(win, tmp, 8u);
        return 1;
    }

    if (cur_char >= SYM_GLYPH_BASE
        && cur_char < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        src = (const uint8_t *)(ADDR_FONT_CHS_SYM
                                + (cur_char - SYM_GLYPH_BASE) * 64u);
        for (i = 0; i < 128u; i++)
            tmp[i] = 0;
        for (i = 0; i < 32u; i++) {
            tmp[0x00 + i] = src[i];
            tmp[0x20 + i] = src[32u + i];
        }
        DrawGlyph_Chinese_Adv(win, tmp, 8u);
        return 1;
    }

    return draw_jp_via_chs(win, cur_char);
}

static const uint8_t *phrase_stream_lookup(uint16_t code)
{
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint32_t off = offsets[code];

    if (off >= 0x01000000u)
        return 0;
    return table + off;
}

static int phrase_stream_no_wait_controls(const uint8_t *stream)
{
    unsigned i = 0;

    if (!stream)
        return 0;
    while (stream[i] != 0xFF) {
        if (stream[i] == CHS_ESCAPE) {
            if (stream[i + 1] != 0)
                return 0;
            i += 4;
            if (i > 256u)
                return 0;
            continue;
        }
        if (stream[i] >= 0xFAu)
            return 0;
        i++;
    }
    return 1;
}

static int phrase_parent_continues(const uint8_t *text, uint16_t index)
{
    return text[index + 3] != 0xFF;
}

static int inline_phrase_no_controls(TextPrinter *win, uint16_t index, uint16_t code)
{
    const uint8_t *stream = phrase_stream_lookup(code);
    unsigned i = 0;
    unsigned n = 0;

    if (!stream || !phrase_stream_no_wait_controls(stream))
        return 0;

    while (stream[i] != 0xFF) {
        if (stream[i] == CHS_ESCAPE && stream[i + 1] == 0) {
            uint8_t lead = stream[i + 2];
            uint8_t trail = stream[i + 3];
            uint16_t gidx;
            if (!lead_trail_ok(lead, trail))
                return 0;
            gidx = pack_glyph_index(lead, trail);
            if (gidx < CHS_FONT_GLYPH_MAX)
                DrawGlyph_Chinese(win, glyph_ptr(gidx));
            i += 4;
        } else {
            if (!draw_chs_pcs(win, stream[i]))
                return 0;
            i++;
        }
        if (++n > 32u)
            break;
    }
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
    return 1;
}

static void redirect_phrase_stream(TextPrinter *win, uint16_t code)
{
    const uint8_t *stream = phrase_stream_lookup(code);

    if (!stream)
        return;
    win_set_u32(win, WIN_TEXT_PTR, (uint32_t)(uintptr_t)stream);
    win_set_u16(win, WIN_TEXT_INDEX, 0);
}

static void expand_1bpp_tile(const uint8_t *src8, uint8_t *dst32)
{
    unsigned row, col;
    for (row = 0; row < 8u; row++) {
        uint8_t bits = src8[row];
        uint32_t out = 0;
        for (col = 0; col < 8u; col++) {
            if (bits & (uint8_t)(0x80u >> col))
                out |= 0xFu << (col * 4u);
        }
        dst32[row * 4u + 0u] = (uint8_t)(out);
        dst32[row * 4u + 1u] = (uint8_t)(out >> 8);
        dst32[row * 4u + 2u] = (uint8_t)(out >> 16);
        dst32[row * 4u + 3u] = (uint8_t)(out >> 24);
    }
}

static int draw_jp_via_chs(TextPrinter *win, uint32_t cur_char)
{
    uint8_t *upper = 0;
    uint8_t *lower = 0;
    uint8_t tmp[128];
    uint8_t font;
    unsigned i;

    if (cur_char == 0 || cur_char >= 0xF7)
        return 0;
    if (cur_char == 0xB5u || cur_char == 0xB6u)
        return 0;
    if (cur_char == 0xEFu)
        return 0;

    font = win_u8(win, WIN_FONTNUM_REAL);
    if (font > 6u)
        font = FONT_NORMAL_SHADOWED;

    chs_get_glyph_tile_pointers(font, (uint16_t)cur_char, &upper, &lower);
    if (!upper || !lower)
        return 0;

    for (i = 0; i < 128u; i++)
        tmp[i] = 0;

    if (chs_font_is_shadowed(font)) {
        for (i = 0; i < 32u; i++) {
            tmp[0x00 + i] = upper[i];
            tmp[0x20 + i] = lower[i];
        }
    } else {
        expand_1bpp_tile(upper, tmp + 0x00);
        expand_1bpp_tile(lower, tmp + 0x20);
    }

    DrawGlyph_Chinese_Adv(win, tmp, CHS_GLYPH_ADVANCE_JP_PX);
    return 1;
}

/**
 * PrintNextChar_C — F9 优先；可印 JP 必须走 CHS 同池（禁回 FontFunc 双路径）。
 */
int PrintNextChar_C(TextPrinter *win, uint32_t cur_char)
{
    /* textMode 2 / 血条缓冲：交原版 FontFunc[2] */
    if (scene_is_battle_interface_dest(win))
        return 0;

    if (cur_char == 0xEFu) {
        if (DrawMenuCursorEF(win))
            return 1;
        return 0;
    }

    /* ---- F9 协议优先 ---- */
    if (cur_char == CHS_ESCAPE) {
        const uint8_t *text =
            (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        uint16_t index = win_u16(win, WIN_TEXT_INDEX);
        const uint8_t *p = text + index;
        uint8_t op = p[0];

        if (op == 0) {
            uint32_t tptr = win_u32(win, WIN_TEXT_PTR);
            if (index == 1
                && (tptr < ADDR_PHRASE_TABLE || tptr >= ADDR_FONT_CHS_NORMAL))
                chs_bind_pitch_slot(win)->write_op = 0;
            {
                uint8_t lead = p[1];
                uint8_t trail = p[2];
                uint16_t gidx;
                if (!lead_trail_ok(lead, trail))
                    return 0;
                win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
                gidx = pack_glyph_index(lead, trail);
                if (gidx >= CHS_FONT_GLYPH_MAX)
                    return 1;
                DrawGlyph_Chinese(win, glyph_ptr(gidx));
                return 1;
            }
        }

        {
            volatile struct ChineseTileState *st = chs_bind_pitch_slot(win);
            uint16_t code = (uint16_t)((p[1] << 8) | p[2]);
            int parent_cont = phrase_parent_continues(text, index);

            if (op == CHS_PHRASE_DEFAULT || parent_cont) {
                st->write_op = 0;
            } else {
                uint8_t L;
                uint8_t cx;
                st->write_op = op;
                L = *(const uint8_t *)(uintptr_t)(ADDR_STYLE_LEFT + op);
                cx = win_u8(win, WIN_CURSOR_X);
                if (L && cx >= L)
                    win_set_u8(win, WIN_CURSOR_X, (uint8_t)(cx - L));
            }

            if (parent_cont && inline_phrase_no_controls(win, index, code))
                return 1;

            redirect_phrase_stream(win, code);
            return 1;
        }
    }

    /* ---- 普通 JP PCS：同套 CHS 绘制 ---- */
    return draw_chs_pcs(win, cur_char);
}
