/* =====================================================================================
 * text_render.c — render 家族共享原语库（纯机制、零策略）
 *
 * 内容：VRAM tile 寻址 / 32B 拷贝 / nibble 像素件 / 单 tile 合成器。
 * 策略 = render_inplace12（text_render_inplace12.c）。
 * ===================================================================================== */
#include "text_render.h"
#include "text.h"   /* struct TextGlyph（CHS 直拷区）*/

void copy_tile32(void *dst_vram, const void *src_iwram)
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

uint8_t *vram_tile(TextPrinter *win, uint16_t tile)
{
    uint8_t *tpl = win_template(win);
    uint8_t *tile_data = (uint8_t *)(uintptr_t)win_u32(tpl, 0x0C);
    return tile_data + ((uint32_t)tile << 5);
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

/* ------------------------------------------------------------------
 * 单 tile 合成器（原 text.c DrawGlyphTile_ShadowedFont / bak
 * DrawGlyphTile_CHS，两版逐值同构，合一）：
 * 官方 CopyGlyph 重映射到栈上缓冲（15→ink/14→shadow/0→bg，C/D/E 终色，
 * FG 覆盖 ADDR_OPT_FG_COLOR），再按 startPixel/width 合成进 dest tile；
 * gw_end>8 时溢出像素写 spillTile（相邻列）。spillTile=NULL=无溢出。
 * ------------------------------------------------------------------ */
void draw_tile(TextPrinter *win, struct GlyphTileInfo *info, uint8_t *spillTile)
{
    uint32_t temp_words[8];
    uint32_t dest_words[8];
    uint32_t spill_words[8];
    uint8_t *temp = (uint8_t *)temp_words;
    uint8_t *dest_l = (uint8_t *)dest_words;
    uint8_t *spill_l = (uint8_t *)spill_words;
    uint8_t *dest = (uint8_t *)info->dest;
    const uint8_t *src32 = info->src;
    unsigned startPixel = info->startPixel;
    unsigned width = info->width;
    unsigned r, c;
    unsigned gw_end = startPixel + width;
    uint8_t fg_ov = *(volatile uint8_t *)ADDR_OPT_FG_COLOR;
    uint8_t color_c = (fg_ov != 0u) ? fg_ov : win_u8(win, WIN_COLOR_C);
    uint8_t color_d = win_u8(win, WIN_COLOR_D);
    uint8_t color_e = win_u8(win, WIN_COLOR_E);
    int need_spill = (spillTile != 0) && (gw_end > 8u);

    CopyGlyph2bppTo4bpp_Origin(src32, temp, color_c, color_e, color_d);

    if (spillTile == 0 && startPixel == 0u && width == 8u) {
        copy_tile32(dest, temp);
        return;
    }

    {
        const uint32_t *dv = (const uint32_t *)dest;
        for (c = 0; c < 8u; c++)
            dest_words[c] = dv[c];
    }
    if (need_spill) {
        const uint32_t *sv = (const uint32_t *)spillTile;
        for (c = 0; c < 8u; c++)
            spill_words[c] = sv[c];
    }

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
        copy_tile32(spillTile, spill_l);
}

/* ---- CHS 字库参数（自 chinese_text.h 并入）---- */
#define CHS_GLYPH_HALF_BIT   0x8000u
#define CHS_GLYPH_IDX_MASK   0x7FFFu
#define CHS_FONT_GLYPH_MAX   7168

/* =====================================================================
 * §glyph —— 字形源统一解析（每字形字体属性）+ CHS 汉库直拷
 *
 * heritage：CHS 两函数来自 rh-hideout-chinese/pokeemerald-expansion
 * src/chinese_text.c（原 hook/src/chinese_text.c，2026-08-27 并入注销）。
 * 与 upstream 三处差异维持不变：
 *   1) IsChineseChar/IsChinesePunctuation 不移植——汉字由 F9 帧定界状态机隔离；
 *   2) 字库源为 armips 侧载 ADDR_FONT_CHS_NORMAL/SMALL（4bpp 预展开直拷）；
 *   3) 显式传参替代 upstream 全局 gCurGlyph（game.bin 无 .bss）。
 * ===================================================================== */
int GetGlyph(TextPrinter *win, uint32_t code, uint8_t *out128, uint8_t *outWidth)
{
    uint8_t fontNum = win_u8(win, WIN_FONTNUM_REAL);
    if (fontNum > 6u)
        fontNum = 3u;    /* bak DrawGlyph_JP_ViaCHS 钳制：非法 fontNum 回落 font3 */

    /* ---- 空白 ---- */
    if (code == 0) {
        unsigned i;
        for (i = 0; i < 128u; i++)
            out128[i] = 0;
        *outWidth = 8u;
        return 1;
    }

    /* ---- Sym 标点带 ---- */
    if (code >= SYM_GLYPH_BASE && code < SYM_GLYPH_BASE + SYM_GLYPH_COUNT) {
        const uint8_t *src = (const uint8_t *)(ADDR_FONT_CHS_SYM
                                               + (code - SYM_GLYPH_BASE) * 64u);
        unsigned i;
        for (i = 0; i < 32u; i++) {
            out128[0x00 + i] = src[i];
            out128[0x20 + i] = src[32u + i];
        }
        for (i = 0; i < 64u; i++)
            out128[0x40 + i] = 0;
        *outWidth = 8u;
        return 1;
    }

    /* ---- 日文 fontNum 字库（官方 GGTP；宽度恒 8px） ---- */
    {
        uint8_t *upper = 0;
        uint8_t *lower = 0;

        if (code >= 0xF7)
            return 0;
        GetGlyphTilePointers_Origin(fontNum, (uint16_t)code, &upper, &lower);
        if (!upper || !lower)
            return 0;

        for (unsigned i = 0; i < 64u; i++)
            out128[0x40 + i] = 0;
        if (FontIsShadowed(fontNum)) {
            copy_tile32(out128 + 0x00, upper);
            copy_tile32(out128 + 0x20, lower);
        } else {
            CopyGlyph1bppTo4bpp_Origin(upper, (uint32_t *)(uintptr_t)(out128 + 0x00), 0xFu, 0x0u);
            CopyGlyph1bppTo4bpp_Origin(lower, (uint32_t *)(uintptr_t)(out128 + 0x20), 0xFu, 0x0u);
        }
        *outWidth = 8u;
        return 1;
    }
}

void DecompressGlyph_Chinese(struct TextGlyph *glyph, uint16_t ChineseChar, uint8_t fontId)
{
    const uint8_t *base;
    const uint8_t *g;

    if (ChineseChar >= CHS_FONT_GLYPH_MAX)
        ChineseChar = 0;

    /* 根据字体类别选择字库（upstream 同款分支；fontId 语义对齐原生 fontNum）：
     * font4（队伍名等小字窗）→ FontChsSmall 8px；其余 → FontChsNormal 12px。 */
    base = (fontId == 4u) ? (const uint8_t *)ADDR_FONT_CHS_SMALL
                          : (const uint8_t *)ADDR_FONT_CHS_NORMAL;
    g = base + ((uint32_t)(ChineseChar & CHS_GLYPH_IDX_MASK) << 7);
    if (ChineseChar & CHS_GLYPH_HALF_BIT)
        g += 64u;

    /* 本工程字模布局：TL+0 / BL+32 / TR+64 / BR+96（各 32B tile）。
     * 填入 upstream struct TextGlyph 行主序：Top = TL|TR，Bottom = BL|BR。 */
    copy_tile32(&glyph->gfxBufferTop[0], g + 0u);
    copy_tile32(&glyph->gfxBufferTop[8], g + 64u);
    copy_tile32(&glyph->gfxBufferBottom[0], g + 32u);
    copy_tile32(&glyph->gfxBufferBottom[8], g + 96u);

    glyph->width = GetChineseFontWidthFunc(ChineseChar, fontId);
    glyph->height = (fontId == 4u) ? 8u : 12u;
}

/* 根据字体类别返回字宽（upstream 同名；本工程汉字宽 = 库定宽，无逐字表）。 */
uint8_t GetChineseFontWidthFunc(uint16_t ChineseChar, uint8_t fontId)
{
    (void)ChineseChar;
    switch (fontId) {
    case 4u:
        return 8u;   /* FontChsSmall：与原生 font4 半角小字同节奏 */
    default:
        return 12u;  /* FontChsNormal：12px 产品字宽 */
    }
}
