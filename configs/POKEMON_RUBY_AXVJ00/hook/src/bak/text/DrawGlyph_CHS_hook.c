/* DrawGlyph_CHS_hook.c — 单字节可印字符（Sym 标点 / 空白 / JP PCS）的 CHS 绘制。
 *
 * 命名对齐 pokeruby DrawGlyph_* 家族。字模来源：
 *   00        → 空白 tile（推进 8px）
 *   0x36..3E  → CHS Sym 带（ADDR_FONT_CHS_SYM，64B/glyph：上排+下排）
 *   其它可印  → 官方 GetGlyphTilePointers（fontNum 分派）+ 1bpp 走官方
 *               CopyGlyph1bppTo4bpp 展开；8px 步进经 CHS 同池绘制。
 */
#include "game.h"

static int DrawGlyph_JP_ViaCHS(TextPrinter *win, uint32_t cur_char);

int DrawGlyph_CHS(TextPrinter *win, uint32_t cur_char)
{
    const uint8_t *src;
    uint32_t tmp_words[32];
    uint8_t *tmp = (uint8_t *)tmp_words;
    unsigned i;

    if (cur_char == 0) {
        for (i = 0; i < 128u; i++)
            tmp[i] = 0;
        PrintGlyph_Tiles_CHS_Adv(win, tmp, 8u);
        return 1;
    }

    if (cur_char >= SYM_GLYPH_BASE
        && cur_char < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        src = (const uint8_t *)(ADDR_FONT_CHS_SYM
                                + (cur_char - SYM_GLYPH_BASE) * 64u);
        for (i = 0; i < 128u; i++)
            tmp[i] = 0;
        for (i = 0; i < 32u; i++) {
            tmp[0x00 + i] = src[i];
            tmp[0x20 + i] = src[32u + i];
        }
        PrintGlyph_Tiles_CHS_Adv(win, tmp, 8u);
        return 1;
    }

    return DrawGlyph_JP_ViaCHS(win, cur_char);
}

/* JP PCS → 官方 GetGlyphTilePointers 取字模，CHS 同池 8px 步进绘制。 */
static int DrawGlyph_JP_ViaCHS(TextPrinter *win, uint32_t cur_char)
{
    uint8_t *upper = 0;
    uint8_t *lower = 0;
    uint32_t tmp_words[32];
    uint8_t *tmp = (uint8_t *)tmp_words;
    uint8_t font;
    unsigned i;

    if (cur_char == 0 || cur_char >= 0xF7)
        return 0;
    if (cur_char == 0xB5u || cur_char == 0xB6u)
        return 0;
    if (cur_char == 0xEFu)
        return 0;

    font = win_u8(win, WIN_FONTNUM_REAL);
    if (font > 6u)
        font = FONT_NORMAL_SHADOWED;

    chs_get_glyph_tile_pointers(font, (uint16_t)cur_char, &upper, &lower);
    if (!upper || !lower)
        return 0;

    for (i = 0; i < 128u; i++)
        tmp[i] = 0;

    if (chs_font_is_shadowed(font)) {
        for (i = 0; i < 32u; i++) {
            tmp[0x00 + i] = upper[i];
            tmp[0x20 + i] = lower[i];
        }
    } else {
        /* 官方 CopyGlyph1bppTo4bpp：1bpp 8B → 4bpp 32B（fg=15, bg=0，
         * 与旧自实现 expand_1bpp_tile 输出逐位一致）。 */
        chs_copy_glyph_1bpp_to_4bpp(upper, (uint32_t *)(uintptr_t)(tmp + 0x00), 0xFu, 0x0u);
        chs_copy_glyph_1bpp_to_4bpp(lower, (uint32_t *)(uintptr_t)(tmp + 0x20), 0xFu, 0x0u);
    }

    PrintGlyph_Tiles_CHS_Adv(win, tmp, CHS_GLYPH_ADVANCE_JP_PX);
    return 1;
}
