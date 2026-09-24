/* DrawGlyph scene routing */
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

/** charBase2 + font3 menu pool → Mode2 (shop_desc excluded). */
int scene_menu_wants_mode2(TextPrinter *win)
{
    uint8_t *tpl = win_template(win);
    if (!tpl || tpl[1] != 2)
        return 0;
    if (win_u8(win, WIN_FONTNUM_REAL) != 3)
        return 0;
    if (scene_is_shop_desc(win))
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
 * Mode2 layout (write.op upper config unchanged):
 * - op 0x02 footer: MENU origin + FOOTER_BAND + y'=y-16 + x++
 * - party DoWhat geometry: shop origin(+2) + PARTY_FOOTER_BAND + y'=y-16, no x++
 * - left≥20 AND y≥13: MENU_BAND + y'=y-13 + origin 0x20 + x++（仅队伍选项）
 * - save/续关等 left≥20 但 y 小：vanilla origin+2，无 BAND
 * - shop list: origin=+2, no BAND
 */
void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin)
{
    volatile struct ChineseTileState *st = chinese_tile_state();
    uint8_t op = st->write_op;
    uint8_t left = win_u8(win, WIN_CURSOR_X);

    *band = 0;
    *origin = CHS_MODE2_ORIGIN_SHOP;

    if (op == CHS_WRITE_FOOTER) {
        *origin = CHS_MODE2_ORIGIN_MENU;
        if (*y >= 16) {
            *y -= 16;
            *band = CHS_MODE2_FOOTER_BAND;
            (*x)++;
        }
        return;
    }
    if (scene_is_party_footer(win)) {
        *origin = CHS_MODE2_ORIGIN_SHOP;
        if (*y >= 16) {
            *y -= 16;
            *band = CHS_MODE2_PARTY_FOOTER_BAND;
        }
        return;
    }
    if (op != 0)
        return;
    /* Party options only: left≥20 AND y≥13. Save/continue (left≥20, y small)
     * must keep vanilla origin+2 / no BAND — else tile indices → 乱码. */
    if (left >= CHS_PARTY_MENU_LEFT && *y >= CHS_PARTY_MENU_TOP) {
        (*x)++;
        *y -= CHS_PARTY_MENU_TOP;
        *band = CHS_MODE2_MENU_BAND;
        *origin = CHS_MODE2_ORIGIN_MENU;
    }
}

int scene_battle_force_linear(TextPrinter *win)
{
    return win_u16(win, WIN_TILE_BASE) >= CHS_BATTLE_FIXED_BASE;
}

/**
 * AXVJ RenderTextHandleBold (0x08002CC0) forces textMode=2; FontFunc[2]
 * blits via win+0x20 into eBattleInterfaceGfxBuffer (healthbox nick/HP).
 * Dest-range gate alone did not fire in-product; textMode==2 is the signal.
 * Summary/dialogue use other modes → JP-via-CHS.
 */
int scene_is_battle_interface_dest(TextPrinter *win)
{
    return win_u8(win, WIN_TEXTMODE) == 2u;
}

/**
 * JP/digit PCS share the CHS tile allocator except FontFunc[2] bold path.
 */
int scene_jp_via_chs(TextPrinter *win)
{
    return !scene_is_battle_interface_dest(win);
}

int scene_keep_linear_16(TextPrinter *win)
{
    /* TEMPORARILY off: shop_desc used top==13 / 0x68 and caught the title
     * menu ? DrawGlyph_Linear16 (CURSOR +=2) so spacing looked like classic 16.
     * Battle fixed-base still needs care via tile pool, but must NOT force
     * advance-16. Product path is fontpatch12 only. */
    (void)win;
    return 0;
}
