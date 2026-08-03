#include "chs.h"

/** 把一角 8×8（0x20 字节）经原版函数拷到指定 tile */
static void copy_tile(TextPrinter *win, const uint8_t *src, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, 0x0C);
    void *dst = tile_data + ((uint32_t)tile << 5);
    chs_copy_glyph_2bpp_to_4bpp(
        src, dst,
        win_u8(win, WIN_COLOR_C),
        win_u8(win, WIN_COLOR_E),
        win_u8(win, WIN_COLOR_D));
}

/** Mode2：由光标算上下两块 tile 编号（含 footer/菜单 band） */
static void compute_cursor_tile_pair(TextPrinter *win, uint16_t *upper, uint16_t *lower)
{
    int x = (int)win_u8(win, WIN_CURSOR_X) + (int)win_u8(win, WIN_CURSOR_TILE_X);
    int y = (int)win_u8(win, WIN_CURSOR_Y) + (int)win_u8(win, WIN_CURSOR_TILE_Y);
    int band = 0;

    chs_party_apply_mode2_band(win, &x, &y, &band);

    uint32_t idx = (uint32_t)(y * CHS_TILE_GRID_W + x + band);
    idx += win_u16(win, WIN_TILE_BASE);
    idx += CHS_MODE2_ORIGIN;
    *upper = (uint16_t)idx;
    *lower = (uint16_t)(idx + CHS_TILE_GRID_W);
}

/** 线性路径：分配本窗相对 tile 偏移（全局水位在 ChineseTileState+4） */
static uint16_t alloc_linear_tile(TextPrinter *win)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    volatile struct ChineseTileState *st = chinese_tile_state();

    if (tile_base >= CHS_BATTLE_FIXED_BASE)
        return win_u16(win, WIN_TILE_OFFSET);

    uint8_t *tpl = win_template(win);
    uint8_t char_base = tpl ? tpl[1] : 0;

    if (char_base != st->char_base) {
        st->char_base = char_base;
        st->write_op = 0;
        if (char_base == 2)
            st->next_abs = (uint16_t)(tile_base + CHS_MENU_LINEAR_FLOOR);
        else
            st->next_abs = (uint16_t)(tile_base + 4);
    }

    uint32_t abs_want = (uint32_t)tile_base + win_u16(win, WIN_TILE_OFFSET);
    if (abs_want < st->next_abs)
        abs_want = st->next_abs;

    uint16_t local = (uint16_t)(abs_want - tile_base);

    if (local >= CHS_TILE_POOL_END) {
        if (st->char_base == 0) {
            local = CHS_LINEAR_STICKY_END;
            st->next_abs = (uint16_t)(tile_base + CHS_LINEAR_STICKY_END);
        } else if (st->char_base == 2) {
            local = CHS_MENU_LINEAR_FLOOR;
            st->next_abs = (uint16_t)(tile_base + CHS_MENU_LINEAR_FLOOR);
        } else {
            local = (uint16_t)(CHS_TILE_POOL_END - 4);
        }
    }

    if (st->char_base == 2) {
        if (local < CHS_MENU_LINEAR_FLOOR)
            local = CHS_MENU_LINEAR_FLOOR;
    } else if (local < 4) {
        local = 4;
    }
    return local;
}

/** 画字形的一列（上+下两块 tile），src_off=0 或 0x40 */
static void draw_linear_column(TextPrinter *win, const uint8_t *src, unsigned src_off)
{
    uint16_t abs_tile = (uint16_t)(win_u16(win, WIN_TILE_BASE) + win_u16(win, WIN_TILE_OFFSET));
    uint16_t upper = abs_tile;
    uint16_t lower = (uint16_t)(abs_tile + 1);
    copy_tile(win, src + src_off, upper);
    copy_tile(win, src + src_off + 0x20, lower);
    chs_update_tilemap(win, upper, lower);
}

/** 线性绘制整字（两列），并推进光标与水位 */
void chs_draw_linear(TextPrinter *win, const uint8_t *src)
{
    uint16_t local = alloc_linear_tile(win);
    win_set_u16(win, WIN_TILE_OFFSET, local);

    draw_linear_column(win, src, 0);
    win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2));
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1));

    draw_linear_column(win, src, 0x40);
    win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(win_u16(win, WIN_TILE_OFFSET) + 2));
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1));

    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    if (tile_base >= CHS_BATTLE_FIXED_BASE)
        return;

    volatile struct ChineseTileState *st = chinese_tile_state();
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    if (off >= CHS_TILE_POOL_END && st->char_base == 0) {
        off = CHS_LINEAR_STICKY_END;
        win_set_u16(win, WIN_TILE_OFFSET, off);
    }
    uint32_t abs_hw = (uint32_t)tile_base + off;
    if (abs_hw > st->next_abs)
        st->next_abs = (uint16_t)abs_hw;
}

/** Mode2 网格绘制整字（两列，按光标格子） */
void chs_draw_mode2(TextPrinter *win, const uint8_t *src)
{
    uint16_t upper, lower;

    compute_cursor_tile_pair(win, &upper, &lower);
    copy_tile(win, src, upper);
    copy_tile(win, src + 0x20, lower);
    chs_update_tilemap(win, upper, lower);
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1));

    compute_cursor_tile_pair(win, &upper, &lower);
    copy_tile(win, src + 0x40, upper);
    copy_tile(win, src + 0x60, lower);
    chs_update_tilemap(win, upper, lower);
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1));
}

/**
 * 分流：战斗/sticky 03·04 → Linear；02/网格 → Mode2；
 * auto → 队伍菜单 Mode2，否则 Linear（商店对话）。
 */
int chs_should_use_linear(TextPrinter *win, uint8_t write_op)
{
    if (chs_battle_force_linear(win))
        return 1;
    if (write_op == CHS_WRITE_GRID || write_op == CHS_WRITE_FOOTER)
        return 0;
    if (write_op == CHS_WRITE_LINEAR || write_op == CHS_WRITE_SLOT)
        return 1;
    if (chs_party_wants_mode2(win))
        return 0;
    if (chs_field_wants_linear(win))
        return 1;
    return 1;
}

/** 绘制入口：charBase 变化时清 sticky，再按策略画 */
void DrawChineseGlyph4bpp(TextPrinter *win, const uint8_t *glyph_src)
{
    volatile struct ChineseTileState *st = chinese_tile_state();
    uint8_t *tpl = win_template(win);
    uint8_t char_base = tpl ? tpl[1] : 0;

    if (char_base != st->char_base) {
        st->char_base = char_base;
        st->write_op = 0;
    }

    if (chs_should_use_linear(win, st->write_op))
        chs_draw_linear(win, glyph_src);
    else
        chs_draw_mode2(win, glyph_src);
}
