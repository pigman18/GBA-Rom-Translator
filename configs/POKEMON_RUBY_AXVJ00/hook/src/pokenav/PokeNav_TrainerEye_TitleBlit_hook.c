/* PokeNav_TrainerEye_TitleBlit_hook — 红条标题 80925BC 兼容入口。
 *
 * dest 布局：每带 0x100B = 上 4 列×0x20 + 下 4 列@+0x80（同 80925BC）。
 *
 * bot 实证（origin 131.ram D1E4）：红条底为满铺 0x11（调色板色 1=红）；
 * 字模侧为高半字节白/阴影。用 c1=1 当墨色会与红底同色而隐形。
 * 本钩：先按带宽预填 0x11，墨迹写 0x0F。
 */
#include "game.h"
#include "text_grid.h"

#define COL_STRIDE    0x20u
#define ROW_STRIDE    0x80u
#define BAND_STRIDE   0x100u
#define COLS_PER_BAND 4u
#define DEST_MAX      0x800u
#define RED_FILL      0x11u
#define FG_WHITE      0xFu
#define PREFILL_BANDS 4u /* origin 前 4 带满 0x11 */

static void paint32(uint8_t *dst, const uint8_t *src, uint8_t fg)
{
    unsigned i;

    for (i = 0u; i < 32u; i++) {
        uint8_t s = src[i];
        uint8_t lo = (uint8_t)(s & 0x0Fu);
        uint8_t hi = (uint8_t)(s >> 4);
        uint8_t out = RED_FILL;
        /* 无墨：红底；有墨：该半字节改白（origin 字模侧 0xE/0xF） */
        if (lo)
            out = (uint8_t)((out & 0xF0u) | fg);
        if (hi)
            out = (uint8_t)((out & 0x0Fu) | (uint8_t)(fg << 4));
        dst[i] = out;
    }
}

static void fill_col(uint8_t *dest, unsigned di)
{
    unsigned i;

    if (di + COL_STRIDE > DEST_MAX)
        return;
    for (i = 0u; i < 32u; i++) {
        dest[di + i] = RED_FILL;
        if (di + ROW_STRIDE + i < DEST_MAX)
            dest[di + ROW_STRIDE + i] = RED_FILL;
    }
}

static void blit_col_at(uint8_t *dest, unsigned di, const uint8_t *tl,
                        const uint8_t *bl, uint8_t fg)
{
    if (di + COL_STRIDE > DEST_MAX)
        return;
    fill_col(dest, di);
    paint32(dest + di, tl, fg);
    if (di + ROW_STRIDE + 32u <= DEST_MAX)
        paint32(dest + di + ROW_STRIDE, bl, fg);
}

static unsigned next_di(unsigned *band, unsigned *col)
{
    unsigned di;

    if (*col >= COLS_PER_BAND) {
        (*band)++;
        *col = 0u;
    }
    di = (*band) * BAND_STRIDE + (*col) * COL_STRIDE;
    (*col)++;
    return di;
}

void PokeNav_TrainerEye_TitleBlit_hook_C(uint8_t *str, uint8_t *dest,
                                         uint32_t c1, uint32_t c2)
{
    unsigned band;
    unsigned col;
    unsigned i;
    uint8_t fg;

    (void)c1;
    (void)c2;
    if (!str || !dest)
        return;

    /* 红条底：与 origin 预填一致 */
    for (i = 0u; i < PREFILL_BANDS * BAND_STRIDE && i < DEST_MAX; i++)
        dest[i] = RED_FILL;

    fg = FG_WHITE;
    band = 0u;
    col = 0u;
    for (i = 0u; str[i] != 0xFFu; ) {
        if (str[i] == 0xF7u && str[i + 1u] == 0x00u) {
            uint16_t gidx = (uint16_t)(GRID_LEAD_ADJUST(str[i + 2u]) * 256u
                                       + (unsigned)str[i + 3u]);
            const uint8_t *g;
            unsigned di;

            if (gidx >= GRID_GLYPH_SLOTS)
                break;
            if (band >= (DEST_MAX / BAND_STRIDE))
                break;
            g = (const uint8_t *)(uintptr_t)ADDR_FONT_CHS_NORMAL
                + (uint32_t)gidx * GRID_GLYPH_BYTES;
            di = next_di(&band, &col);
            blit_col_at(dest, di, g, g + 32u, fg);
            di = next_di(&band, &col);
            blit_col_at(dest, di, g + 64u, g + 96u, fg);
            i += 4u;
        } else {
            unsigned di = next_di(&band, &col);
            fill_col(dest, di);
            i += 1u;
        }
    }
}
