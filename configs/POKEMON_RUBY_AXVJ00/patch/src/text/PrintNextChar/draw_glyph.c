/* Gen3 Chinese draw: 8x16 hardware tile columns (16-tall slot), 12px metrics.
 *
 * ROM glyph = 128B 4bpp TL,BL,TR,BR (Font_Patch layout).
 * Advance = CHS_GLYPH_ADVANCE_PX (12) via Font_Patch 8+4.
 *
 * Color via JP CopyGlyph2bppTo4bpp (IWRAM scratch → CpuSet).
 * NEVER byte-store into VRAM (GBA mirrors both bytes of a halfword → 重影).
 * Compose in IWRAM, then copy_tile32 to VRAM.
 * Linear floor: field 0x100 / shop_desc 0x228. Mode2: MENU_BAND only left≥20 & y≥13.
 */
#include "game.h"

static void copy_tile32(void *dst_vram, const void *src_iwram)
{
    const uint32_t *s = (const uint32_t *)src_iwram;
    uint32_t *d = (uint32_t *)dst_vram;
    d[0] = s[0];
    d[1] = s[1];
    d[2] = s[2];
    d[3] = s[3];
    d[4] = s[4];
    d[5] = s[5];
    d[6] = s[6];
    d[7] = s[7];
}

static void pitch_reset(TextPrinter *win)
{
    volatile struct ChineseTileState *st = chinese_tile_state();
    st->chs_px = 0;
    st->base_tx = win_u8(win, WIN_CURSOR_TILE_X);
}

static uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, 0x0C);
    return tile_data + ((uint32_t)tile << 5);
}

/* Field Linear @ 0x100 / shop_desc @ 0x228 — see configs/docs/CHS_TILE_LAYOUT.md */
static void ensure_linear_dest_floor(TextPrinter *win)
{
    uint8_t *tpl;
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t floor;

    if (tile_base >= CHS_BATTLE_FIXED_BASE)
        return;

    tpl = win_template(win);
    if (scene_is_shop_desc(win))
        floor = CHS_SHOP_DESC_LINEAR_FLOOR;
    else if (tpl && tpl[1] == 2)
        floor = CHS_MENU_LINEAR_FLOOR;
    else
        floor = 4;

    if (off < floor)
        win_set_u16(win, WIN_TILE_OFFSET, floor);
}

static uint16_t linear_cursor_tile(TextPrinter *win, unsigned x_off, unsigned y_off)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    return (uint16_t)(tile_base + off + 2u * x_off + y_off);
}

static void compute_mode2_pair(
    TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
{
    int x = (int)win_u8(win, WIN_CURSOR_X) + tile_x;
    int y = (int)win_u8(win, WIN_CURSOR_Y) + (int)win_u8(win, WIN_CURSOR_TILE_Y);
    int band = 0;
    int origin = CHS_MODE2_ORIGIN_SHOP;
    uint8_t *tpl = win_template(win);

    if (!tpl || tpl[1] != 2)
        origin = 0;
    scene_mode2_apply(win, &x, &y, &band, &origin);
    {
        uint32_t idx = (uint32_t)(y * CHS_TILE_GRID_W + x + band);
        idx += win_u16(win, WIN_TILE_BASE);
        idx += (uint32_t)origin;
        *upper = (uint16_t)idx;
        *lower = (uint16_t)(idx + CHS_TILE_GRID_W);
    }
}

static uint8_t get_px(const uint8_t *tile, unsigned x, unsigned y)
{
    unsigned bi = y * 4u + x / 2u;
    if (x & 1u)
        return (uint8_t)(tile[bi] & 0x0Fu);
    return (uint8_t)(tile[bi] >> 4);
}

static void put_px(uint8_t *tile, unsigned x, unsigned y, uint8_t ink)
{
    unsigned bi = y * 4u + x / 2u;
    if (x & 1u)
        tile[bi] = (uint8_t)((tile[bi] & 0xF0u) | (ink & 0x0Fu));
    else
        tile[bi] = (uint8_t)((tile[bi] & 0x0Fu) | ((ink & 0x0Fu) << 4));
}

/*
 * Remap via ROM CopyGlyph (15→C ink, 14→E shadow, 0→D bg) then place at startPixel.
 * All pixel work stays in IWRAM; VRAM only receives 32-bit word copies.
 *
 * GBA VRAM 禁止 byte 写入（会 mirror 到半字另一字节导致鬼影）。
 * 所有像素合成在栈上 IWRAM（temp/dest_l/spill_l）完成，最后通过
 * copy_tile32 以 8 次 32-bit word copy 刷入 VRAM。
 *
 * spill 机制：当 startPixel + width > 8 时（因 12px advance 必然
 * 跨 tile 列），need_spill=1，同时处理当前 tile 和下一 tile 的
 * IWRAM 副本。清像素列 → OR 墨水 → 两 tile 分别写回 VRAM。
 */
static void draw_glyph_tile_12(
    TextPrinter *win,
    uint8_t *dest, uint8_t *spill, const uint8_t src32[32],
    unsigned startPixel, unsigned width)
{
    uint32_t temp_words[8];
    uint32_t dest_words[8];
    uint32_t spill_words[8];
    uint8_t *temp = (uint8_t *)temp_words;
    uint8_t *dest_l = (uint8_t *)dest_words;
    uint8_t *spill_l = (uint8_t *)spill_words;
    unsigned r, c;
    unsigned gw_end = startPixel + width;
    uint8_t color_c = win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    int need_spill = (spill != 0) && (gw_end > 8u);

    /* CopyGlyph(C,E,D): 15→ink, 14→shadow, 0→bg. Unshadow font has no 14. */
    chs_copy_glyph_2bpp_to_4bpp(src32, temp, color_c, color_e, color_d);

    /* Fast path: full 8px column, tile-aligned — CopyGlyph buffer → VRAM. */
    if (spill == 0 && startPixel == 0u && width == 8u) {
        copy_tile32(dest, temp);
        return;
    }

    /* Seed from existing VRAM (16-bit-safe read via words) when OR-shifting. */
    {
        const uint32_t *dv = (const uint32_t *)dest;
        for (c = 0; c < 8u; c++)
            dest_words[c] = dv[c];
    }
    if (need_spill) {
        const uint32_t *sv = (const uint32_t *)spill;
        for (c = 0; c < 8u; c++)
            spill_words[c] = sv[c];
    }

    /* Clear only the columns we own, then stamp ink (IWRAM only). */
    for (r = 0; r < 8; r++) {
        for (c = startPixel; c < gw_end && c < 8u; c++)
            put_px(dest_l, c, r, color_d);
        if (need_spill) {
            unsigned from = (startPixel > 8u) ? (startPixel - 8u) : 0u;
            unsigned to = gw_end - 8u;
            for (c = from; c < to && c < 8u; c++)
                put_px(spill_l, c, r, color_d);
        }
        for (c = 0; c < width; c++) {
            unsigned dc = startPixel + c;
            if (dc < 8u)
                put_px(dest_l, dc, r, get_px(temp, c, r));
            else if (need_spill)
                put_px(spill_l, dc - 8u, r, get_px(temp, c, r));
        }
        if (gw_end < 8u) {
            for (c = gw_end; c < 8u; c++)
                put_px(dest_l, c, r, color_d);
        }
        if (need_spill && gw_end > 8u) {
            for (c = gw_end - 8u; c < 8u; c++)
                put_px(spill_l, c, r, color_d);
        }
    }

    copy_tile32(dest, dest_l);
    if (need_spill)
        copy_tile32(spill, spill_l);
}

static void map_at(TextPrinter *win, uint8_t tx, uint16_t abs_u, uint16_t abs_l)
{
    win_set_u8(win, WIN_CURSOR_TILE_X, tx);
    chs_update_tilemap(win, abs_u, abs_l);
}

void drawGlyph12(TextPrinter *win, const uint8_t *src128, int linear)
{
    /*
     * 16px 字模 → 12px advance 的核心实现。
     * GBA 硬件 tile 为 8×8，字模按 4-tile（TL/BL/TR/BR）存储，但光标
     * 推进由 chs_px 累积控制。每字分两趟写入：
     *   趟1（width=8）：取 src128[0x00..0x3F]（左半 TL+BL），从
     *   startPixel = chs_px & 7 起写入 8px。
     *   趟2（width=4）：取 src128[0x40..0x7F]（右半 TR+BR），从同一
     *   startPixel 起写入 4px。
     * 两趟合计 chs_px += 12，下一字的 startPixel = (12+12) & 7 = 0
     * （偶数）或 4（奇数）。宽度总和 8+4=12 正好对齐 GBA tile 边界，
     * 但右 4px 必然跨入下一 tile 列（startPixel + 8 > 8 触发 spill）。
     * spill 处理：draw_glyph_tile_12 先读目标 tile 和 spill tile 的
     * 当前 VRAM 内容到 IWRAM，清掉本字拥有的像素列，再 OR 上墨水像素，
     * 最后 32-bit word copy 回 VRAM。下一字左 4px 覆盖上一字右 4px，
     * 利用汉字外缘空白实现视觉上的紧凑连续排版。
     */
    volatile struct ChineseTileState *st = chinese_tile_state();
    unsigned startPixel;
    uint16_t off, abs_u, abs_l, su, sl;
    uint8_t *du, *dl, *du_sp, *dl_sp;
    uint8_t map_tx;

    if (st->chs_px == 0)
        st->base_tx = win_u8(win, WIN_CURSOR_TILE_X);

    startPixel = (unsigned)(st->chs_px & 7u);
    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    /* ---- pass width 8: TL + BL ---- */
    if (linear) {
        if (st->chs_px == 0)
            ensure_linear_dest_floor(win);
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = linear_cursor_tile(win, 0, 0);
        abs_l = linear_cursor_tile(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            su = linear_cursor_tile(win, 1, 0);
            sl = linear_cursor_tile(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x00, startPixel, 8);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x20, startPixel, 8);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));
    } else {
        compute_mode2_pair(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 8u > 8u) {
            compute_mode2_pair(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x00, startPixel, 8);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x20, startPixel, 8);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + 8u);
    map_tx = (uint8_t)(st->base_tx + (st->chs_px >> 3));

    /* ---- pass width 4: TR + BR ---- */
    if (linear) {
        off = win_u16(win, WIN_TILE_OFFSET);
        abs_u = linear_cursor_tile(win, 0, 0);
        abs_l = linear_cursor_tile(win, 0, 1);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 4u > 8u) {
            su = linear_cursor_tile(win, 1, 0);
            sl = linear_cursor_tile(win, 1, 1);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x40, startPixel, 4);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x60, startPixel, 4);
        map_at(win, map_tx, abs_u, abs_l);
        win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + (startPixel == 0u ? 0u : 2u)));
    } else {
        compute_mode2_pair(win, (int)map_tx, &abs_u, &abs_l);
        du = vram_tile(win, abs_u);
        dl = vram_tile(win, abs_l);
        if (startPixel + 4u > 8u) {
            compute_mode2_pair(win, (int)map_tx + 1, &su, &sl);
            du_sp = vram_tile(win, su);
            dl_sp = vram_tile(win, sl);
        } else {
            du_sp = 0;
            dl_sp = 0;
        }
        draw_glyph_tile_12(win, du, du_sp, src128 + 0x40, startPixel, 4);
        draw_glyph_tile_12(win, dl, dl_sp, src128 + 0x60, startPixel, 4);
        map_at(win, map_tx, abs_u, abs_l);
    }

    st->chs_px = (uint16_t)(st->chs_px + 4u);
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(st->base_tx + (st->chs_px >> 3)));
}

int DrawGlyph_ShouldUseLinear(TextPrinter *win, uint8_t write_op)
{
    uint8_t *tpl;

    if (scene_battle_force_linear(win))
        return 1;
    /* charBase2 menu pool: Mode2 must win over inject LINEAR (F9 03).
     * Field start-menu labels lived under 战斗菜单 → F9 03; Linear + Print
     * rewind shares one floor so every row shows the last string (often 关闭).
     * shop_desc keeps Linear (scene_menu_wants_mode2 == 0). */
    if (scene_menu_wants_mode2(win))
        return 0;
    if (write_op == CHS_WRITE_LINEAR || write_op == CHS_WRITE_SLOT)
        return 1;
    if (write_op == CHS_WRITE_GRID || write_op == CHS_WRITE_FOOTER)
        return 0;
    tpl = win_template(win);
    /* Non-menu charBase (field/battle templates): linear bump. */
    if (!tpl || tpl[1] != 2)
        return 1;
    /* Remaining charBase2 (shop_desc only after Mode2 gate above). */
    if (scene_is_shop_desc(win))
        return 1;
    return 0;
}

void DrawGlyph_Chinese(TextPrinter *win, const uint8_t *glyph_src)
{
    volatile struct ChineseTileState *st = chinese_tile_state();
    uint8_t *tpl = win_template(win);
    uint8_t char_base = tpl ? tpl[1] : 0;
    uint8_t cur_tx = win_u8(win, WIN_CURSOR_TILE_X);
    int linear;

    if (char_base != st->char_base) {
        st->char_base = char_base;
        st->write_op = 0;
        pitch_reset(win);
    } else if (st->chs_px != 0) {
        uint8_t expect = (uint8_t)(st->base_tx + (st->chs_px >> 3));
        if (cur_tx != expect)
            pitch_reset(win);
    } else {
        st->base_tx = cur_tx;
    }

    linear = DrawGlyph_ShouldUseLinear(win, st->write_op);
    drawGlyph12(win, glyph_src, linear);
}
