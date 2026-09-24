/* text_scene.c — 认窗 if + 三处效应；不做政策机 */
#include "text_scene.h"

uint8_t chs_pitch_write_op(TextPrinter *win);

/* ---- route ---- */

int scene_is_buffer_printer(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);

    if (win_u8(win, WIN_TEXTMODE) == 2u)
        return 1;
    if (!tpl || win_u8(win, WIN_TEXTMODE) != 1u)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 4u)
        return 0;
    return win_u32(tpl, TPL_TILEMAP) == 0u;
}

int scene_delegate_buffer_print(TextPrinter *win)
{
    /* 跳板 → ROM 0x08003300（entry.s）；勿再对旧 incbin 副本取址 */
    return PrintNextChar_Origin(win);
}

int scene_jp_via_chs(TextPrinter *win)
{
    return win_u8(win, WIN_TEXTMODE) != 2u;
}

/* ---- 认窗（只回答是不是） ---- */

static int screen_summary(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);

    return tpl && ((uintptr_t)tpl & ~1u) == (uintptr_t)CHS_SUMMARY_TEMPLATE;
}

static int screen_battle(TextPrinter *win)
{
    uint16_t tb = win_u16(win, WIN_TILE_BASE);

    if (tb == CHS_BATTLE_DIALOG_BASE_LO)
        return 1;
    if (tb >= CHS_BATTLE_TEXT_BASE_LO && tb < CHS_BATTLE_TEXT_BASE_HI)
        return 1;
    return tb >= CHS_BATTLE_FIXED_BASE;
}

static int screen_party_footer(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t y;

    if (!tpl || tpl[1] != 2 || win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    if (win_u8(win, WIN_CURSOR_X) >= CHS_SHOP_LIST_LEFT)
        return 0;
    y = win_u8(win, WIN_CURSOR_Y);
    return y == CHS_PARTY_FOOTER_TOP_TILE || y == CHS_PARTY_FOOTER_TOP_PX;
}

static int screen_shop_desc(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t y;

    if (!tpl || tpl[1] != 2 || win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    if (win_u8(win, WIN_CURSOR_X) >= CHS_SHOP_LIST_LEFT)
        return 0;
    if (screen_party_footer(win))
        return 0;
    y = win_u8(win, WIN_CURSOR_Y);
    return y == CHS_SHOP_DESC_TOP_PX || y == CHS_SHOP_DESC_TOP_TILE;
}

static int screen_shop_bag(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    const uint8_t *g;
    uint8_t left;
    uint16_t tb;

    if (!tpl || tpl[1] != 2 || win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    if (screen_shop_desc(win) || screen_party_footer(win))
        return 0;
    left = win_u8(win, WIN_CURSOR_X);
    tb = win_u16(win, WIN_TILE_BASE);
    if (left == 2u && tb >= 0x80u && tb < 0x120u)
        return 1;
    if (left == 7u && tb >= 0x60u && tb < 0x90u)
        return 1;
    g = (const uint8_t *)ADDR_GMENU;
    if (g[GMENU_LEFT] == 1u && g[GMENU_TOP] == 1u && g[GMENU_MAX_MINUS_1] >= 6u
        && (left == 2u || left == 7u))
        return 1;
    return 0;
}

static int screen_menu_mode2(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t cb;

    if (!tpl || win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    cb = tpl[1];
    if (cb != 0 && cb != 2)
        return 0;
    if (screen_summary(win) || screen_shop_desc(win) || screen_shop_bag(win))
        return 0;
    return 1;
}

/* ---- 效应 ---- */

int scene_should_use_linear(TextPrinter *win, uint8_t write_op)
{
    (void)write_op;
    if ((win_u8(win, WIN_TEXTMODE) & 7u) == 0u)
        return 1;
    if (screen_battle(win))
        return 1;
    if (screen_shop_desc(win) || screen_shop_bag(win))
        return 1;
    if (screen_menu_mode2(win))
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) == FONT_NORMAL_SHADOWED)
        return 0;
    return 1;
}

void scene_apply_linear_floor(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t floor;

    if (screen_battle(win))
        return;
    if (screen_party_footer(win))
        floor = CHS_PARTY_FOOTER_LINEAR_FLOOR;
    else if (screen_shop_bag(win))
        floor = CHS_SHOP_LIST_LINEAR_FLOOR;
    else if (screen_shop_desc(win))
        floor = CHS_SHOP_DESC_LINEAR_FLOOR;
    else if (tpl && tpl[1] == 2)
        floor = CHS_MENU_LINEAR_FLOOR;
    else
        floor = 4;
    if (off < floor)
        win_set_u16(win, WIN_TILE_OFFSET, floor);
}

uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile)
{
    if (screen_battle(win))
        return tile;
    if (screen_summary(win)) {
        if (tile >= CHS_UI_ICON_TILE_LO && tile <= CHS_UI_ICON_TILE_HI)
            return (uint16_t)(CHS_UI_ICON_TILE_ALT + (tile - CHS_UI_ICON_TILE_LO));
        if (tile >= CHS_PSS_B_VRAM_LO && tile <= CHS_PSS_B_VRAM_HI)
            return (uint16_t)(CHS_PSS_B_VRAM_ALT + (tile - CHS_PSS_B_VRAM_LO));
        return tile;
    }
    if (tile >= CHS_MENU_CURSOR_TILE && tile <= CHS_MENU_CURSOR_TILE_HI)
        return (uint16_t)(CHS_MENU_CURSOR_TILE_ALT + (tile - CHS_MENU_CURSOR_TILE));
    if (tile >= CHS_UI_ICON_TILE_LO && tile <= CHS_UI_ICON_TILE_HI)
        return (uint16_t)(CHS_UI_ICON_TILE_ALT + (tile - CHS_UI_ICON_TILE_LO));
    return tile;
}

static void mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin)
{
    uint8_t op = chs_pitch_write_op(win);
    uint8_t left = win_u8(win, WIN_CURSOR_X);

    *band = 0;
    *origin = CHS_MODE2_ORIGIN_SHOP;

    if (screen_party_footer(win)) {
        if (*y >= CHS_PARTY_FOOTER_TOP_PX)
            *y /= 8;
        if (*y >= 16) {
            *y -= 16;
            *band = CHS_MODE2_PARTY_FOOTER_BAND;
        }
        return;
    }
    if (screen_summary(win))
        return;
    if (op != 0)
        return;
    if (*y <= 20 && (*y & 1) == 0)
        return;
    if (left >= CHS_PARTY_MENU_LEFT && *y >= CHS_PARTY_MENU_TOP) {
        (*x)++;
        *y -= CHS_PARTY_MENU_TOP;
        *band = CHS_MODE2_MENU_BAND;
        *origin = CHS_MODE2_ORIGIN_MENU;
    }
}

uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff)
{
    return scene_remap_tile(
        win,
        (uint16_t)(win_u16(win, WIN_TILE_BASE) + win_u16(win, WIN_TILE_OFFSET)
                   + 2u * xOff + yOff));
}

void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
{
    int x = (int)win_u8(win, WIN_CURSOR_X) + tile_x;
    int y = (int)win_u8(win, WIN_CURSOR_Y) + (int)win_u8(win, WIN_CURSOR_TILE_Y);
    int band = 0;
    int origin = CHS_MODE2_ORIGIN_SHOP;
    uint8_t *tpl = win_template(win);
    uint32_t idx;

    if (!tpl || tpl[1] != 2)
        origin = 0;
    mode2_apply(win, &x, &y, &band, &origin);
    idx = (uint32_t)(y * CHS_TILE_GRID_W + x + band);
    idx += win_u16(win, WIN_TILE_BASE);
    idx += (uint32_t)origin;
    *upper = scene_remap_tile(win, (uint16_t)idx);
    *lower = scene_remap_tile(win, (uint16_t)(idx + CHS_TILE_GRID_W));
}
