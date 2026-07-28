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

/* Sym bank: 16×16 2bpp (64B). CHS draw wants 128B TL/BL/TR/BR 4bpp (0/E/F). */
static uint8_t sym_pix2(const uint8_t *g64, unsigned x, unsigned y)
{
    unsigned bitpos = y * 16u + x;
    uint8_t byte = g64[bitpos >> 2];
    unsigned shift = (bitpos & 3u) * 2u;
    return (uint8_t)((byte >> shift) & 3u);
}

static void put_nib4(uint8_t *tile32, unsigned x, unsigned y, uint8_t nib)
{
    unsigned bi = y * 4u + x / 2u;
    if (x & 1u)
        tile32[bi] = (uint8_t)((tile32[bi] & 0xF0u) | (nib & 0x0Fu));
    else
        tile32[bi] = (uint8_t)((tile32[bi] & 0x0Fu) | ((nib & 0x0Fu) << 4));
}

static uint8_t sym_val_to_nib(uint8_t v)
{
    if (v >= 3u)
        return 0x0Fu; /* ink */
    if (v == 2u)
        return 0x0Eu; /* shadow */
    return 0;
}

static void sym64_to_chs128(uint8_t out[128], const uint8_t *g64)
{
    unsigned i, x, y;
    for (i = 0; i < 128u; i++)
        out[i] = 0;
    for (y = 0; y < 16u; y++) {
        for (x = 0; x < 16u; x++) {
            uint8_t nib = sym_val_to_nib(sym_pix2(g64, x, y));
            uint8_t *tile;
            if (y < 8u)
                tile = out + ((x < 8u) ? 0x00u : 0x40u);
            else
                tile = out + ((x < 8u) ? 0x20u : 0x60u);
            put_nib4(tile, x & 7u, y & 7u, nib);
        }
    }
}

static int draw_sym_punct(TextPrinter *win, uint32_t cur_char)
{
    const uint8_t *src;
    uint8_t tmp[128];

    if (cur_char < SYM_GLYPH_BASE || cur_char >= SYM_GLYPH_BASE + SYM_GLYPH_COUNT)
        return 0;
    src = (const uint8_t *)(ADDR_FONT_CHS_SYM
                            + (cur_char - SYM_GLYPH_BASE) * 64u);
    sym64_to_chs128(tmp, src);
    DrawGlyph_Chinese(win, tmp);
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
 * PrintNextChar_C — GBA 文字渲染引擎的 CJK 扩展入口。
 *
 * 调用时机：原版 ProcessCurrentChar 检测到 ROM 中的 F9 逃逸码时
 * 通过 hook（main.asm）跳转到此函数。受管指令格式：
 *   F9 00 ll tt   单 CJK 字 — lead/trail 编码 → pack_glyph_index → glyph_ptr
 *   F9 7F hi lo   短语（通用）— 重置 write_op=0 → draw_phrase(code)
 *   F9 01..7E hi lo 短语（带 write_op）
 *                   — st->write_op = op（01=物种/grid, 04=招式/slot, etc.）
 *                   → draw_phrase(code)，op 影响 drawGlyph12 的模式选择
 *
 * F9 00 受字段 stride 限制：每字 4 字节，8 字节槽最多 2 汉字。
 * 短语模式（F9 7F/op）将文本移到 PhraseTable 扩展区，槽内只存 4 字节
 * 引用，突破长度限制（详见 game.h:ADDR_PHRASE_OFFSETS 注释）。
 *
 * 渲染后端：DrawGlyph_Chinese → drawGlyph12（16px 字模 + 12px advance）。
 *
 * @return 0=未处理（交由原版 FontFuncTable 继续），1=已由本函数完成
 */
int PrintNextChar_C(TextPrinter *win, uint32_t cur_char)
{
    ensure_linear_tile_bump(win);

    /* Single-byte Sym punct (。、，！？ …): do not use JP Font3. */
    if (draw_sym_punct(win, cur_char))
        return 1;

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
