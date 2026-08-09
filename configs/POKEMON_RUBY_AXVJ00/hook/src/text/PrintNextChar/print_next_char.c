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
 * Mid-string F9 phrase must not EOS the parent (JP placeholder semantics).
 * GetStringWidth skips the 4B ref and keeps walking; print matches via inline.
 * No PhraseResume EWRAM (F7F8/FFF0 both unsafe — map corrupt / boot crash).
 */
static const uint8_t *phrase_stream_lookup(uint16_t code)
{
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint32_t off = offsets[code];

    if (off >= 0x01000000u)
        return 0;
    return table + off;
}

/* No FE/FB/FA — safe to inline (species F9 00×N, or place JP digits+F9 00). */
static int phrase_stream_no_wait_controls(const uint8_t *stream)
{
    unsigned i = 0;

    if (!stream)
        return 0;
    while (stream[i] != 0xFF) {
        if (stream[i] == CHS_ESCAPE) {
            if (stream[i + 1] != 0)
                return 0; /* nested phrase ref */
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

/* Parent continues after F9 op hi lo (battle expand); else whole-string phrase. */
static int phrase_parent_continues(const uint8_t *text, uint16_t index)
{
    return text[index + 3] != 0xFF;
}

/* forward — defined below with JP-via-CHS path */
static int draw_jp_via_chs(TextPrinter *win, uint32_t cur_char);

/*
 * Draw phrase onto current window; keep WIN_TEXT_PTR on parent; INDEX += 3.
 * Used when parent continues (species-in-battle). Whole-string map names
 * still redirect (one glyph/frame) — no EWRAM walk state.
 */
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
            /* JP digit/punct inside place-like streams — only for parent_cont. */
            if (!draw_jp_via_chs(win, stream[i]))
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

    /* Gender: FontFunc. EF handled in PrintNextChar_C via DrawMenuCursorEF. */
    if (cur_char == 0xB5u || cur_char == 0xB6u)
        return 0;
    if (cur_char == 0xEFu)
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

    if (cur_char == 0xEFu) {
        if (DrawMenuCursorEF(win))
            return 1;
        return 0;
    }

    /* FE/FB/FA are handled in PCC control jumptable — they never reach this
     * RegularGlyph hook. Wait-arrow sync is WaitArrow_Prepare_C @ 0x3F4C.
     * Pitch reset after FE happens on next glyph via pitch_key / cur_tx. */

    if (draw_sym_punct(win, cur_char))
        return 1;

    if (cur_char != CHS_ESCAPE) {
        /* Printable → JP-via-CHS (digits included; F9 00 / 表内流同路). */
        return draw_jp_via_chs(win, cur_char);
    }

    {
        const uint8_t *text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        uint16_t index = win_u16(win, WIN_TEXT_INDEX);
        const uint8_t *p = text + index;
        uint8_t op = p[0];

        if (op == 0) {
            /* 串首 F9 00 清 sticky；PhraseTable 流内首字勿清（保留 F9 op 的 write_op）。 */
            {
                uint32_t tptr = win_u32(win, WIN_TEXT_PTR);
                if (index == 1
                    && (tptr < ADDR_PHRASE_TABLE || tptr >= ADDR_FONT_CHS_NORMAL))
                    chinese_tile_state()->write_op = 0;
            }
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
            int parent_cont;

            code = (uint16_t)((p[1] << 8) | p[2]);
            parent_cont = phrase_parent_continues(text, index);

            if (op == CHS_PHRASE_DEFAULT) {
                st->write_op = 0;
            } else if (parent_cont) {
                /* Mid-string species/etc: StyleLeft is for whole-field labels
                 * (dex). Nudging here backs up into 野生的 → glitch tile. */
                st->write_op = 0;
            } else {
                uint8_t L;
                uint8_t cx;
                st->write_op = op;
                /* StyleLeft[op]: one-shot X nudge for whole-string phrase. */
                L = *(const uint8_t *)(uintptr_t)(ADDR_STYLE_LEFT + op);
                cx = win_u8(win, WIN_CURSOR_X);
                if (L && cx >= L)
                    win_set_u8(win, WIN_CURSOR_X, (uint8_t)(cx - L));
            }

            /* Mid-string (battle \03): inline so phrase FF does not EOS parent. */
            if (parent_cont && inline_phrase_no_controls(win, index, code))
                return 1;

            /* Whole-string phrase (map name) or controls inside phrase. */
            redirect_phrase_stream(win, code);
            return 1;
        }
    }
}
