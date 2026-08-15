/* DrawGlyphTiles_scene — layout gates for DrawGlyphTiles_hook (AXVJ). */
#include "game.h"

/**
 * Party DoWhat at (1,17): often F9 00 after \0F.
 * Mode2 with y'=y-16 + PARTY_FOOTER_BAND, origin=+2 (same grid as nick).
 */
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

/**
 * Legacy helper. DrawGlyph_ShouldUseLinear no longer forces Linear on
 * left<14 (that caught title/shop multichoice → shared-tile 串台).
 */
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

/** Font3 Mode2 grid: charBase 0 (naming SoftKeyboard/title) or 2 (menus).
 * SoftKeyboard BG1 is charBase 0 — requiring only charBase2 forced Linear and
 * aliased every keyboard row + title onto the same low Linear tiles. */
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

/**
 * Shop buy / bag item rows — Mode2 grid can stomp window-frame tiles.
 * Keep Linear (cursor ▶ uses CHS_MENU_CURSOR_TILE, not the shared pool).
 *
 * Narrow gates (continue-screen left=2 must NOT match):
 * - Bag names/qty: high TILE_BASE from bag printers (0x8A… / 0x66…)
 * - Shop+bag while InitMenu(1,1,n≥7) active: names left=2, price/qty left=7
 */
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

    /* Bag item-name printer: TILE_BASE = 0x8A + 14*row */
    if (left == 2u && tile_base >= 0x80u && tile_base < 0x120u)
        return 1;
    /* Bag quantity printer: TILE_BASE = 0x66 / 0x6c / … */
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

/**
 * Mode2 layout (write.op upper config unchanged):
 * - party DoWhat geometry: shop origin(+2) + PARTY_FOOTER_BAND + y'=y-16
 * - left≥20 AND y≥13: MENU_BAND + y'=y-13 + origin 0x20 + x++（仅队伍选项）
 * - save/续关等 left≥20 但 y 小：vanilla origin+2，无 BAND
 */
void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin)
{
    volatile struct ChineseTileState *st = chs_bind_pitch_slot(win, 0);
    uint8_t op = st->write_op;
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

int scene_is_battle_interface_dest(TextPrinter *win)
{
    return win_u8(win, WIN_TEXTMODE) == 2u;
}

int scene_jp_via_chs(TextPrinter *win)
{
    return !scene_is_battle_interface_dest(win);
}

int scene_keep_linear_16(TextPrinter *win)
{
    (void)win;
    return 0;
}
