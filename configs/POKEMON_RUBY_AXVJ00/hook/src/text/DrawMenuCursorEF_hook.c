/* DrawMenuCursorEF_hook.c — PCS 0xEF ► 菜单光标（InitMenu ▶）。
 *
 * 官方把 ► 当可印字符送 FontFunc；这里把 JP 字模 blit 进
 * CHS_MENU_CURSOR_TILE 固定对，只 map 光标格（不占 CHS 线性池）。
 */
#include "game.h"

int DrawMenuCursorEF(TextPrinter *win)
{
    uint8_t *upper = 0;
    uint8_t *lower = 0;
    uint32_t src_words[32];
    uint8_t *src = (uint8_t *)src_words;
    uint8_t font;
    uint8_t *du;
    uint8_t *dl;
    unsigned i;
    uint16_t abs_u = CHS_MENU_CURSOR_TILE;
    uint16_t abs_l = CHS_MENU_CURSOR_TILE_HI;

    if (!win)
        return 0;

    font = win_u8(win, WIN_FONTNUM_REAL);
    if (font > 6u)
        font = FONT_NORMAL_SHADOWED;
    if (!chs_font_is_shadowed(font))
        return 0;

    chs_get_glyph_tile_pointers(font, 0xEFu, &upper, &lower);
    if (!upper || !lower)
        return 0;

    for (i = 0; i < 128u; i++)
        src[i] = 0;
    for (i = 0; i < 32u; i++) {
        src[0x00 + i] = upper[i];
        src[0x20 + i] = lower[i];
    }

    du = vram_tile(win, abs_u);
    dl = vram_tile(win, abs_l);
    {
        struct GlyphTileInfo info;
        info.textMode = 0;
        info.colors = 0;
        info.startPixel = 0;
        info.width = 8;
        info.dest = (uint32_t *)(uintptr_t)du;
        info.src = src + 0x00;
        DrawGlyphTile_CHS(win, &info, 0);
        info.dest = (uint32_t *)(uintptr_t)dl;
        info.src = src + 0x20;
        DrawGlyphTile_CHS(win, &info, 0);
    }
    chs_update_tilemap(win, abs_u, abs_l);
    win_set_u8(win, WIN_CURSOR_TILE_X,
               (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1u));
    return 1;
}
