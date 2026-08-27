/* text_scene.c — 场景布局门控（bak DrawGlyphTiles_hook.c + SCENE_GATES_AXVJ.md） */
#include "text_scene.h"

uint8_t chs_pitch_write_op(TextPrinter *win);

/* =============================================================================
 * 路由（Layer A）
 * ============================================================================= */

int scene_is_battle_interface_dest(TextPrinter *win)
{
    return win_u8(win, WIN_TEXTMODE) == 2u;
}

static int scene_is_bold_buffer_template(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);

    if (!tpl)
        return 0;
    if (win_u8(win, WIN_TEXTMODE) != 1u)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 4u)
        return 0;
    /*
     * RenderTextHandleBold：template tilemap=NULL，dest=win[0x20]。
     * 队伍名窗 0x081BB43C 同为 win=0x03004170、tm1+font4，但 tilemap=0x0600F000
     * → 必须走引擎 tm1/Origin，误 delegate PrintNextChar_Origin → PC=0x00000004。
     */
    return win_u32(tpl, TPL_TILEMAP) == 0u;
}

int scene_is_buffer_printer(TextPrinter *win)
{
    if (scene_is_battle_interface_dest(win))
        return 1;
    return scene_is_bold_buffer_template(win);
}

int scene_delegate_buffer_print(TextPrinter *win)
{
    typedef int (*pnc_t)(TextPrinter *win);

    return ((pnc_t)((uintptr_t)PrintNextChar_Origin | 1u))(win);
}

int scene_jp_via_chs(TextPrinter *win)
{
    return !scene_is_battle_interface_dest(win);
}

/* =============================================================================
 * 探测器（Layer B）
 * ============================================================================= */

int scene_is_party_footer(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t left;
    uint8_t top;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    left = win_u8(win, WIN_CURSOR_X);
    if (left >= CHS_SHOP_LIST_LEFT)
        return 0;
    top = win_u8(win, WIN_CURSOR_Y);
    return (top == CHS_PARTY_FOOTER_TOP_TILE || top == CHS_PARTY_FOOTER_TOP_PX);
}

int scene_field_wants_linear(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);

    if (!tpl)
        return 0;
    if (tpl[1] != 2)
        return 1;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 1;
    if (scene_is_party_footer(win))
        return 0;
    if (scene_is_shop_desc(win))
        return 1;
    return 0;
}

int scene_menu_wants_mode2(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t char_base;

    if (!tpl)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    char_base = tpl[1];
    if (char_base != 0 && char_base != 2)
        return 0;
    if (scene_is_shop_desc(win))
        return 0;
    if (scene_is_shop_bag_list(win))
        return 0;
    return 1;
}

int scene_is_shop_desc(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    uint8_t left;
    uint8_t top;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    left = win_u8(win, WIN_CURSOR_X);
    if (left >= CHS_SHOP_LIST_LEFT)
        return 0;
    if (scene_is_party_footer(win))
        return 0;
    top = win_u8(win, WIN_CURSOR_Y);
    return (top == CHS_SHOP_DESC_TOP_PX || top == CHS_SHOP_DESC_TOP_TILE);
}

int scene_is_shop_bag_list(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    const uint8_t *gmenu;
    uint8_t left;
    uint16_t tile_base;

    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    if (scene_is_shop_desc(win) || scene_is_party_footer(win))
        return 0;

    left = win_u8(win, WIN_CURSOR_X);
    tile_base = win_u16(win, WIN_TILE_BASE);

    if (left == 2u && tile_base >= 0x80u && tile_base < 0x120u)
        return 1;
    if (left == 7u && tile_base >= 0x60u && tile_base < 0x90u)
        return 1;

    gmenu = (const uint8_t *)ADDR_GMENU;
    if (gmenu[GMENU_LEFT] == 1u && gmenu[GMENU_TOP] == 1u
        && gmenu[GMENU_MAX_MINUS_1] >= 6u) {
        if (left == 2u || left == 7u)
            return 1;
    }
    return 0;
}

int scene_is_battle_text_window(TextPrinter *win)
{
    uint16_t tb = win_u16(win, WIN_TILE_BASE);

    if (tb == CHS_BATTLE_DIALOG_BASE_LO)
        return 1;
    if (tb >= CHS_BATTLE_TEXT_BASE_LO && tb < CHS_BATTLE_TEXT_BASE_HI)
        return 1;
    return tb >= CHS_BATTLE_FIXED_BASE;
}

int scene_battle_force_linear(TextPrinter *win)
{
    return scene_is_battle_text_window(win);
}

/* =============================================================================
 * 布局效应（Layer B）
 * ============================================================================= */

uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile)
{
    if (scene_is_battle_text_window(win))
        return tile;
    if (tile >= CHS_MENU_CURSOR_TILE && tile <= CHS_MENU_CURSOR_TILE_HI)
        return (uint16_t)(CHS_MENU_CURSOR_TILE_ALT
                          + (tile - CHS_MENU_CURSOR_TILE));
    if (tile >= CHS_UI_ICON_TILE_LO && tile <= CHS_UI_ICON_TILE_HI)
        return (uint16_t)(CHS_UI_ICON_TILE_ALT + (tile - CHS_UI_ICON_TILE_LO));
    return tile;
}

void scene_apply_linear_floor(TextPrinter *win)
{
    uint8_t *tpl;
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);
    uint16_t floor;

    if (scene_is_battle_text_window(win))
        return;

    tpl = win_template(win);
    if (scene_is_party_footer(win))
        floor = CHS_PARTY_FOOTER_LINEAR_FLOOR;
    else if (scene_is_shop_bag_list(win))
        floor = CHS_SHOP_LIST_LINEAR_FLOOR;
    else if (scene_is_shop_desc(win))
        floor = CHS_SHOP_DESC_LINEAR_FLOOR;
    else if (tpl && tpl[1] == 2)
        floor = CHS_MENU_LINEAR_FLOOR;
    else
        floor = 4;

    if (off < floor)
        win_set_u16(win, WIN_TILE_OFFSET, floor);
}

uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff)
{
    uint16_t tile_base = win_u16(win, WIN_TILE_BASE);
    uint16_t off = win_u16(win, WIN_TILE_OFFSET);

    return scene_remap_tile(
        win, (uint16_t)(tile_base + off + 2u * xOff + yOff));
}

void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower)
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
        *upper = scene_remap_tile(win, (uint16_t)idx);
        *lower = scene_remap_tile(win, (uint16_t)(idx + CHS_TILE_GRID_W));
    }
}

void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin)
{
    uint8_t op = chs_pitch_write_op(win);
    uint8_t left = win_u8(win, WIN_CURSOR_X);

    *band = 0;
    *origin = CHS_MODE2_ORIGIN_SHOP;

    if (scene_is_party_footer(win)) {
        *origin = CHS_MODE2_ORIGIN_SHOP;
        if (*y >= CHS_PARTY_FOOTER_TOP_PX)
            *y /= 8;
        if (*y >= 16) {
            *y -= 16;
            *band = CHS_MODE2_PARTY_FOOTER_BAND;
        }
        return;
    }
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

int scene_should_use_linear(TextPrinter *win, uint8_t write_op)
{
    if (scene_battle_force_linear(win))
        return 1;
    if (scene_is_shop_desc(win) || scene_is_shop_bag_list(win))
        return 1;
    (void)write_op;
    if (scene_menu_wants_mode2(win))
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) == FONT_NORMAL_SHADOWED)
        return 0;
    return 1;
}

int scene_keep_linear_16(TextPrinter *win)
{
    (void)win;
    return 0;
}
