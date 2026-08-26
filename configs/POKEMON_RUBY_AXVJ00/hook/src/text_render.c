/* =====================================================================================
 * text_render.c — render 家族共享原语库（纯机制、零策略）
 *
 * 内容：VRAM tile 寻址 / 32B 拷贝 / nibble 像素件 / 单 tile 合成器 / 实验选择器。
 * 策略（状态、落点、表项模式）在各 text_render_<策略>.c。
 * ===================================================================================== */
#include "text_render.h"

/* ------------------------------------------------------------------
 * 实验选择器：0x0203FF8C（bak ChsPitchCtrl 的 pad 后、age[8] 之后的
 * 公共空闲字节；现行 ChsPhase 布局亦不占用）。0=默认(inplace12)。
 * ------------------------------------------------------------------ */
render_fn render_active(render_fn dflt)
{
    switch (*(volatile uint8_t *)RENDER_SEL_ADDR) {
    case 1:  return render_band;
    case 2:  return render_inplace12;
    default: return dflt;
    }
}

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
