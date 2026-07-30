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

/*
 * 从 ROM 字库（ADDR_FONT_CHS_NORMAL @ 0x09000000）读取字模。
 * 每字 128B = 4 个 8×8 4bpp tile（TL/BL/TR/BR）
 * 映射为 16×16 bitmap。渲染时 drawGlyph12 只取左 8px + 右 4px，
 * 光标推进 12px，右 4px 跨入下一 tile 列形成 spill 重叠。
 */
static const uint8_t *glyph_ptr(uint16_t index)
{
    /* 128B / glyph: 16x16 4bpp slot (TL,BL,TR,BR) — Gen3 hardware container. */
    return (const uint8_t *)(ADDR_FONT_CHS_NORMAL + ((uint32_t)index << 7));
}

/*
 * Sym bank (9×64B @ ADDR_FONT_CHS_SYM): Font3-layout 8×16 —
 * upper 32B + lower 32B of 4bpp-index tiles (nibble 0/E/F).
 * NOT 16×16 packed 2bpp — that mis-decode vertically stretches 。？.
 */
static int draw_sym_punct(TextPrinter *win, uint32_t cur_char)
{
    const uint8_t *src;
    uint8_t tmp[128];
    unsigned i;

    if (cur_char < SYM_GLYPH_BASE || cur_char >= SYM_GLYPH_BASE + SYM_GLYPH_COUNT)
        return 0;
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

/*
 * 短语表渲染入口。
 * 调用时机：解析到 F9 <op> hi lo（phrase 模式），code = (hi << 8) | lo。
 * 1. PhraseOffsets[code]（u16 @ 0x08810000）→ 条目偏移
 * 2. PhraseTable[offset]（@ 0x08820000）→ {u8 count, u8 pad, u16 idx[count]}
 * 3. 逐字渲染：glyph_ptr(idx) → DrawGlyph_Chinese（12px advance / glyph）
 * 短语表与 F9 00（单字侧载）共享同一渲染后端，区别仅在于字形来源：
 *   F9 00：glyph_ptr(pack_glyph_index(lead, trail))
 *   F9 7F/op：glyph_ptr(phrase_indices[i])
 */
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
 * PrintNextChar_C — CJK + JP-via-CHS (ProcessCurrentChar hook).
 *
 * F9: Chinese sideload / phrase (skipped when textMode==2 → FontFunc).
 * Printable PCS: JP-via-CHS except textMode==2 (FontFunc[2] healthbox).
 * AXVJ GetGlyphTilePointers is 4-arg (font, glyph, &u, &l) — no language.
 */
/* 1bpp row bytes → 32B 4bpp-index tile with ink=0xF (CopyGlyph2bpp-ready). */
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

/* Returns 1 for printable PCS (consumed by CHS path). Controls return 0. */
static int draw_jp_via_chs(TextPrinter *win, uint32_t cur_char)
{
    uint8_t *upper = 0;
    uint8_t *lower = 0;
    uint8_t tmp[128];
    uint8_t font;
    unsigned i;

    if (cur_char == 0 || cur_char >= 0xF7)
        return 0;

    /* textMode 2 = FontFunc[2] bold/healthbox; CHS would write wrong VRAM. */
//    if (scene_is_battle_interface_dest(win))
//        return 0;

    font = win_u8(win, WIN_FONTNUM_REAL);
    /* 0x0B is fontNum; if aliased garbage (>6), fall back to shadowed. */
    if (font > 6u)
        font = FONT_NORMAL_SHADOWED;

    chs_get_glyph_tile_pointers(font, (uint16_t)cur_char, &upper, &lower);
    if (!upper || !lower)
        return 0; /* ABI/lookup fail → original FontFunc (never blank claim) */

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

int PrintNextChar_C(TextPrinter *win, uint32_t cur_char)
{
    ensure_linear_tile_bump(win);

    /* Bold/healthbox: no CHS (incl. sym); FontFunc[2] owns the blit. */
    if (scene_is_battle_interface_dest(win))
        return 0;

    if (draw_sym_punct(win, cur_char))
        return 1;

    if (cur_char != CHS_ESCAPE) {
        /* Printable → JP-via-CHS. Controls → original. */
        return draw_jp_via_chs(win, cur_char);
    }

    {
        const uint8_t *text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        uint16_t index = win_u16(win, WIN_TEXT_INDEX);
        const uint8_t *p = text + index;
        uint8_t op = p[0];

        if (op == 0) {
            if (index == 1)
                chinese_tile_state()->write_op = 0;
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
            volatile struct ChineseTileState *st = chinese_tile_state();
            uint16_t code;
            if (op == CHS_PHRASE_DEFAULT)
                st->write_op = 0;
            else
                st->write_op = op;
            code = (uint16_t)((p[1] << 8) | p[2]);
            win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
            draw_phrase(win, code);
            return 1;
        }
    }
}
