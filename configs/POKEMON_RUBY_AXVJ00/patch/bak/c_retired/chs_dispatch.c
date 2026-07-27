#include "chs.h"

/** 战斗菜单 charBase==0：抬高 WIN_TILE_OFFSET，避免日文昵称盖中文 VRAM */
static void ensure_linear_tile_bump(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    if (!tpl || tpl[1] != 0)
        return;

    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    if (tile_base >= CHS_BATTLE_FIXED_BASE)
        return;

    volatile struct ChineseTileState *st = chinese_tile_state();
    if (st->char_base != 0)
        return;

    uint16_t next = st->next_abs;
    if (next < 4)
        return;
    if (next <= tile_base)
        return;

    uint16_t delta = (uint16_t)(next - tile_base);
    if (delta >= CHS_TILE_POOL_END) {
        delta = CHS_LINEAR_STICKY_END;
        st->next_abs = (uint16_t)(tile_base + CHS_LINEAR_STICKY_END);
    }

    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    if (off < delta)
        win_set_u16(win, WIN_TILE_OFFSET, delta);
}

/** 侧载 F9 00 的 lead/trail 是否像合法中文双字节 */
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

/** lead/trail → 字库线性下标（与旧 asm Cgd_sub1/sub2 一致） */
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

/** 字库中第 index 个字形的 0x80 字节地址 */
static const uint8_t *glyph_ptr(uint16_t index)
{
    return (const uint8_t *)(ADDR_FONT_CHS_NORMAL + ((uint32_t)index << 7));
}

/** 按短语码从 PhraseTable 取字并逐个绘制 */
static void draw_phrase(TextPrinter *win, uint16_t code)
{
    const uint16_t *offsets = (const uint16_t *)ADDR_PHRASE_OFFSETS;
    const uint8_t *table = (const uint8_t *)ADDR_PHRASE_TABLE;
    uint16_t off = offsets[code];
    const uint8_t *entry = table + off;
    uint8_t count = entry[0];
    const uint16_t *indices = (const uint16_t *)(entry + 2);

    for (uint8_t i = 0; i < count; i++)
        DrawChineseGlyph4bpp(win, glyph_ptr(indices[i]));
}

/**
 * F9 分发：侧载单字 / 短语 + sticky。
 * F9 7F（默认短语）只清 write.op，不清 +4 水位（菜单三行共用 Linear）。
 */
int ChineseGlyphDispatch_C(TextPrinter *win, uint32_t cur_char)
{
    ensure_linear_tile_bump(win);

    if (cur_char != CHS_ESCAPE)
        return 0;

    const uint8_t *text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    uint16_t index = win_u16(win, WIN_TEXT_INDEX);
    const uint8_t *p = text + index;
    uint8_t op = p[0];

    if (op == 0) {
        /* F9 00 lead trail — 侧载单字；串首清 sticky */
        if (index == 1) {
            chinese_tile_state()->write_op = 0;
        }
        uint8_t lead = p[1];
        uint8_t trail = p[2];
        if (!lead_trail_ok(lead, trail))
            return 0;

        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
        uint16_t gidx = pack_glyph_index(lead, trail);
        if (gidx >= CHS_FONT_GLYPH_MAX)
            return 1;
        DrawChineseGlyph4bpp(win, glyph_ptr(gidx));
        return 1;
    }

    /* F9 XX hi lo — 短语；XX=7F auto，01..7E 写 sticky */
    volatile struct ChineseTileState *st = chinese_tile_state();
    if (op == CHS_PHRASE_DEFAULT) {
        st->write_op = 0;
    } else {
        st->write_op = op;
        if (op < 3)
            st->next_abs = 0; /* footer(op=2) 清线性水位 */
    }

    uint16_t code = (uint16_t)((p[1] << 8) | p[2]);
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(index + 3));
    draw_phrase(win, code);
    return 1;
}
