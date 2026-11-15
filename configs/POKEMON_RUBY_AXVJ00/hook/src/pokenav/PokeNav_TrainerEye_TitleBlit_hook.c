/* PokeNav_TrainerEye_TitleBlit_hook — 红条标题 80925BC 兼容入口。
 *
 * dest 布局：每带 0x100B = 上 4 列×0x20 + 下 4 列@+0x80（同 80925BC）。
 *
 * bot 实证（origin 131.ram D1E4）：红条底为满铺 0x11（调色板色 1=红）；
 * 字模侧为高半字节白/阴影。用 c1=1 当墨色会与红底同色而隐形。
 * 本钩：先按带宽预填 0x11，墨迹写 0x0F。
 *
 * 度量：12px 步进（8+4），与产品 CHS_GLYPH_ADVANCE_PX 一致；
 * 不再一字占两整列（16px）。与列表残墨无关（用户确认）。
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
#define PREFILL_BANDS 8u /* 12px 更密，多预填几带红底 */
#define ADVANCE_PX    12u
#define GLYPH_W       12u
#define GLYPH_H       16u

static unsigned di_for_col(unsigned col)
{
    unsigned band = col / COLS_PER_BAND;
    unsigned cin = col % COLS_PER_BAND;
    return band * BAND_STRIDE + cin * COL_STRIDE;
}

/* 在 dest 像素 (sx,sy) 写一墨点（4bpp 低半字节=左）。超出 dest 则丢弃。 */
static void put_px(uint8_t *dest, unsigned sx, unsigned sy, uint8_t fg)
{
    unsigned col, di, row, idx;
    uint8_t *p;

    if (sy >= GLYPH_H)
        return;
    col = sx >> 3;
    if (di_for_col(col) + COL_STRIDE > DEST_MAX)
        return;
    di = di_for_col(col);
    row = sy;
    if (row >= 8u) {
        di += ROW_STRIDE;
        row -= 8u;
        if (di + COL_STRIDE > DEST_MAX)
            return;
    }
    /* 8×8 tile：每行 4 字节，字节内 lo=偶像素、hi=奇像素 */
    idx = row * 4u + ((sx & 7u) >> 1);
    p = dest + di + idx;
    if ((sx & 1u) == 0u)
        *p = (uint8_t)((*p & 0xF0u) | (fg & 0x0Fu));
    else
        *p = (uint8_t)((*p & 0x0Fu) | (uint8_t)((fg & 0x0Fu) << 4));
}

/* 字库半字节：lo=左。只把非 0 墨画到 dest，红底保留在无墨处。 */
static uint8_t glyph_px(const uint8_t *g, unsigned gx, unsigned gy)
{
    const uint8_t *tile;
    unsigned lx, ly, idx;
    uint8_t b;

    if (gx >= 16u || gy >= 16u)
        return 0u;
    /* TL(0) BL(32) TR(64) BR(96)；每块 8×8 */
    if (gy < 8u)
        tile = g + ((gx < 8u) ? 0u : 64u);
    else
        tile = g + ((gx < 8u) ? 32u : 96u);
    lx = gx & 7u;
    ly = gy & 7u;
    idx = ly * 4u + (lx >> 1);
    b = tile[idx];
    if ((lx & 1u) == 0u)
        return (uint8_t)(b & 0x0Fu);
    return (uint8_t)(b >> 4);
}

static void blit_glyph_12(uint8_t *dest, unsigned px, const uint8_t *g,
                          uint8_t fg)
{
    unsigned gx, gy;
    uint8_t v;

    for (gy = 0u; gy < GLYPH_H; gy++) {
        for (gx = 0u; gx < GLYPH_W; gx++) {
            v = glyph_px(g, gx, gy);
            if (v)
                put_px(dest, px + gx, gy, fg);
        }
    }
}

void PokeNav_TrainerEye_TitleBlit_hook_C(uint8_t *str, uint8_t *dest,
                                         uint32_t c1, uint32_t c2)
{
    unsigned i;
    unsigned px;
    uint8_t fg;

    (void)c1;
    (void)c2;
    if (!str || !dest)
        return;

    for (i = 0u; i < PREFILL_BANDS * BAND_STRIDE && i < DEST_MAX; i++)
        dest[i] = RED_FILL;

    fg = FG_WHITE;
    px = 0u;
    for (i = 0u; str[i] != 0xFFu; ) {
        if (str[i] == 0xF7u && str[i + 1u] == 0x00u) {
            uint16_t gidx = (uint16_t)(GRID_LEAD_ADJUST(str[i + 2u]) * 256u
                                       + (unsigned)str[i + 3u]);
            const uint8_t *g;

            if (gidx >= GRID_GLYPH_SLOTS)
                break;
            if (px + GLYPH_W > (DEST_MAX / COL_STRIDE) * 8u)
                break;
            g = (const uint8_t *)(uintptr_t)ADDR_FONT_CHS_NORMAL
                + (uint32_t)gidx * GRID_GLYPH_BYTES;
            blit_glyph_12(dest, px, g, fg);
            px += ADVANCE_PX;
            i += 4u;
        } else {
            /* PCS/空格：推进 8px，保持红底 */
            px += 8u;
            i += 1u;
        }
    }
}
