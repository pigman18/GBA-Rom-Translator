/* PokeNav_TrainerEye_TitleBlit_hook — 红条标题 80925BC 兼容入口。
 *
 * dest 布局：每带 0x100B = 上 4 列×0x20 + 下 4 列@+0x80（同 80925BC）。
 *
 * bot 实证（origin 131.ram D1E4）：红条底为满铺 0x11（调色板色 1=红）；
 * 字模侧为高半字节白/阴影。用 c1=1 当墨色会与红底同色而隐形。
 *
 * 本钩：预填 0x11；中文走 Middle（9×11）+ 12px 水平步进（相位贴 4bpp），
 * 与正文 Menu_PrintText 的 tile-Y 行距无关——红条是自有像素缓冲。
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
#define PREFILL_BANDS 4u
#define TITLE_ADV_PX  12u
#define GLYPH_W       16u
#define GLYPH_H       16u

static uint8_t *col_base(uint8_t *dest, unsigned col, unsigned row8)
{
    unsigned band = col / COLS_PER_BAND;
    unsigned cin = col % COLS_PER_BAND;
    unsigned off = band * BAND_STRIDE + cin * COL_STRIDE;

    if (row8)
        off += ROW_STRIDE;
    if (off + COL_STRIDE > DEST_MAX)
        return 0;
    return dest + off;
}

/* 4bpp：一行 4B=8px；低半字节=偶像素，高半字节=奇像素（与 paint32 一致）。 */
static void put_px(uint8_t *dest, unsigned x, unsigned y, uint8_t fg)
{
    uint8_t *base;
    unsigned row8;
    unsigned yi;
    unsigned xi;
    uint8_t *cell;
    uint8_t shift;

    if (x >= (DEST_MAX / BAND_STRIDE) * COLS_PER_BAND * 8u || y >= GLYPH_H)
        return;
    row8 = (y >= 8u) ? 1u : 0u;
    yi = y & 7u;
    base = col_base(dest, x >> 3, row8);
    if (!base)
        return;
    xi = x & 7u;
    cell = base + yi * 4u + (xi >> 1);
    shift = (uint8_t)((xi & 1u) ? 4u : 0u);
    *cell = (uint8_t)((*cell & (uint8_t)(0xF0u >> shift)) | (uint8_t)(fg << shift));
}

static uint8_t glyph_px(const uint8_t *g, unsigned sx, unsigned sy)
{
    const uint8_t *tile;
    unsigned row;
    unsigned col;
    uint8_t b;

    if (sx >= GLYPH_W || sy >= GLYPH_H)
        return 0u;
    /* TL 0 / BL 32 / TR 64 / BR 96 */
    tile = g + ((sy >= 8u) ? 32u : 0u) + ((sx >= 8u) ? 64u : 0u);
    row = sy & 7u;
    col = sx & 7u;
    b = tile[row * 4u + (col >> 1)];
    return (uint8_t)((col & 1u) ? (b >> 4) : (b & 0x0Fu));
}

static void blit_glyph_at(uint8_t *dest, unsigned x0, const uint8_t *g,
                          uint8_t fg)
{
    unsigned sx;
    unsigned sy;

    for (sy = 0u; sy < GLYPH_H; sy++) {
        for (sx = 0u; sx < TITLE_ADV_PX; sx++) {
            if (glyph_px(g, sx, sy))
                put_px(dest, x0 + sx, sy, fg);
        }
    }
}

void PokeNav_TrainerEye_TitleBlit_hook_C(uint8_t *str, uint8_t *dest,
                                         uint32_t c1, uint32_t c2)
{
    unsigned i;
    unsigned x;
    uint8_t fg;
    unsigned max_x;

    (void)c1;
    (void)c2;
    if (!str || !dest)
        return;

    for (i = 0u; i < PREFILL_BANDS * BAND_STRIDE && i < DEST_MAX; i++)
        dest[i] = RED_FILL;

    fg = FG_WHITE;
    x = 0u;
    max_x = PREFILL_BANDS * COLS_PER_BAND * 8u;
    for (i = 0u; str[i] != 0xFFu; ) {
        if (str[i] == 0xF7u && str[i + 1u] == 0x00u) {
            uint16_t gidx = (uint16_t)(GRID_LEAD_ADJUST(str[i + 2u]) * 256u
                                       + (unsigned)str[i + 3u]);
            const uint8_t *g;

            if (gidx >= GRID_GLYPH_SLOTS)
                break;
            if (x + TITLE_ADV_PX > max_x)
                break;
            g = (const uint8_t *)(uintptr_t)ADDR_FONT_CHS_MIDDLE
                + (uint32_t)gidx * GRID_GLYPH_BYTES;
            blit_glyph_at(dest, x, g, fg);
            x += TITLE_ADV_PX;
            i += 4u;
        } else {
            /* 日文/空格：占 8px 空列（红底已预填） */
            if (x + 8u > max_x)
                break;
            x += 8u;
            i += 1u;
        }
    }
}
