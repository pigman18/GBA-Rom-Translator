/* ============================================================================
 * blend_glyph.c — 混合写入像素原语（语义照抄官方 DrawGlyphTile_UnshadowedFont）
 *
 * 实现说明：
 *   - sGlyphMasks / sGlyphShiftAmounts 与官方 pokeruby text.c 同表（vendored
 *     副本 reference/pokeruby/draw_glyph_tile.c；tests/test_blend_glyph.py
 *     会直接从该文件解析本表并逐位对拍，防转录走样）；
 *   - 官方 9 个 ShiftGlyphTile_*_WidthN 特化函数收敛为一个通用循环——
 *     展开字形行得到 val（低 nibble = 最左像素，nibbles [0,width) 有效），
 *     RMW 骨架完全一致：
 *       首 tile:  dest[r] = (dest[r] & mask1) | (val << left)
 *       溢出 tile: spill[r] = (spill[r] & mask2) | (val >> right)
 *     与官方逐位等价（对拍 harness 佐证），只是不再展开 9 份代码；
 *   - width==0 官方为无操作（掩码全保留 + Width0 空函数），此处提前返回；
 *     startPixel>7 / width>8 钳制（官方越界未定义，调用方本就不该传）。
 * ==========================================================================*/
#include "blend_glyph.h"

/* 官方 sGlyphMasks[width][startPixel] = { 首tile保留掩码, 溢出tile保留掩码,
 * (与[0]同或合成首tile掩码) }。语义：首 tile 跨度 [startPixel, startPixel+
 * width) 内清底重写、跨度外保留；溢出 tile 掩码按官方表原样引用（含边角）。 */
static const uint32_t sGlyphMasks[9][8][3] =
{
    {
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
        { 0xFFFFFFFF,0xFFFFFFFF,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFFFFF0, },
        { 0x0000000F,0xFFFFFFFF,0xFFFFFF00, },
        { 0x000000FF,0xFFFFFFFF,0xFFFFF000, },
        { 0x00000FFF,0xFFFFFFFF,0xFFFF0000, },
        { 0x0000FFFF,0xFFFFFFFF,0xFFF00000, },
        { 0x000FFFFF,0xFFFFFFFF,0xFF000000, },
        { 0x00FFFFFF,0xFFFFFFFF,0xF0000000, },
        { 0x0FFFFFFF,0xFFFFFFFF,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFFFF00, },
        { 0x0000000F,0xFFFFFFFF,0xFFFFF000, },
        { 0x000000FF,0xFFFFFFFF,0xFFFF0000, },
        { 0x00000FFF,0xFFFFFFFF,0xFFF00000, },
        { 0x0000FFFF,0xFFFFFFFF,0xFF000000, },
        { 0x000FFFFF,0xFFFFFFFF,0xF0000000, },
        { 0x00FFFFFF,0xFFFFFFFF,0x00000000, },
        { 0x0FFFFFFF,0xFFFFFFF0,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFFF000, },
        { 0x0000000F,0xFFFFFFFF,0xFFFF0000, },
        { 0x000000FF,0xFFFFFFFF,0xFFF00000, },
        { 0x00000FFF,0xFFFFFFFF,0xFF000000, },
        { 0x0000FFFF,0xFFFFFFFF,0xF0000000, },
        { 0x000FFFFF,0xFFFFFFFF,0x00000000, },
        { 0x00FFFFFF,0xFFFFFFF0,0x00000000, },
        { 0x0FFFFFFF,0xFFFFFF00,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFFF0000, },
        { 0x0000000F,0xFFFFFFFF,0xFFF00000, },
        { 0x000000FF,0xFFFFFFFF,0xFF000000, },
        { 0x00000FFF,0xFFFFFFFF,0xF0000000, },
        { 0x0000FFFF,0xFFFFFFFF,0x00000000, },
        { 0x000FFFFF,0xFFFFFFF0,0x00000000, },
        { 0x00FFFFFF,0xFFFFFF00,0x00000000, },
        { 0x0FFFFFFF,0xFFFFF000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFFF00000, },
        { 0x0000000F,0xFFFFFFFF,0xFF000000, },
        { 0x000000FF,0xFFFFFFFF,0xF0000000, },
        { 0x00000FFF,0xFFFFFFFF,0x00000000, },
        { 0x0000FFFF,0xFFFFFFF0,0x00000000, },
        { 0x000FFFFF,0xFFFFFF00,0x00000000, },
        { 0x00FFFFFF,0xFFFFF000,0x00000000, },
        { 0x0FFFFFFF,0xFFFF0000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xFF000000, },
        { 0x0000000F,0xFFFFFFFF,0xF0000000, },
        { 0x000000FF,0xFFFFFFFF,0x00000000, },
        { 0x00000FFF,0xFFFFFFF0,0x00000000, },
        { 0x0000FFFF,0xFFFFFF00,0x00000000, },
        { 0x000FFFFF,0xFFFFF000,0x00000000, },
        { 0x00FFFFFF,0xFFFF0000,0x00000000, },
        { 0x0FFFFFFF,0xFFF00000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0xF0000000, },
        { 0x0000000F,0xFFFFFFFF,0x00000000, },
        { 0x000000FF,0xFFFFFFF0,0x00000000, },
        { 0x00000FFF,0xFFFFFF00,0x00000000, },
        { 0x0000FFFF,0xFFFFF000,0x00000000, },
        { 0x000FFFFF,0xFFFF0000,0x00000000, },
        { 0x00FFFFFF,0xFFF00000,0x00000000, },
        { 0x0FFFFFFF,0xFF000000,0x00000000, },
    },
    {
        { 0x00000000,0xFFFFFFFF,0x00000000, },
        { 0x0000000F,0xFFFFFFF0,0x00000000, },
        { 0x000000FF,0xFFFFFF00,0x00000000, },
        { 0x00000FFF,0xFFFFF000,0x00000000, },
        { 0x0000FFFF,0xFFFF0000,0x00000000, },
        { 0x000FFFFF,0xFFF00000,0x00000000, },
        { 0x00FFFFFF,0xFF000000,0x00000000, },
        { 0x0FFFFFFF,0xF0000000,0x00000000, },
    },
};

static const struct GlyphShiftAmount {
    uint32_t left;
    uint32_t right;
} sGlyphShiftAmounts[8] =
{
    {  0, 32 },
    {  4, 28 },
    {  8, 24 },
    { 12, 20 },
    { 16, 16 },
    { 20, 12 },
    { 24,  8 },
    { 28,  4 },
};

/* RMW 骨架（官方等价）。expand_row：把第 r 行字形展开为 nibble 序（低 nibble
 * = 最左像素，nibbles [0,width) 有效，其余为 0）。 */

/* 1bpp：rows[r] bit7 = 最左像素（官方 unshadowed 字模序），bit=0 → colors[0]。
 * 上游怪癖（照抄保逐位等价）：官方 ShiftGlyphTile_UnshadowedFont_Width3 实际
 * 展开 4 个像素（pret 源码自带 "XXX: why 4?" 注释）——顺序文本下该多余 nibble
 * 会被下一字形的跨度重写即时覆盖，死代码；固定 8px 宽度下永不触发。 */
static uint32_t blend_row_1bpp(const uint8_t *rows, uint32_t r,
                               uint32_t width, const uint8_t *colors)
{
    uint8_t bits = rows[r];
    uint32_t val = 0;
    uint32_t p;
    uint32_t n = (width == 3u) ? 4u : width;

    for (p = 0; p < n; p++)
        val |= (uint32_t)colors[(bits >> (7u - p)) & 1u] << (p * 4u);

    return val;
}

/* 2bpp：GBA 序——rows[2r] 起每字节低 2 位 = 最左像素 */
static uint32_t blend_row_2bpp(const uint8_t *rows, uint32_t r,
                               uint32_t width, const uint8_t *colors)
{
    const uint8_t *row = &rows[r * 2u];
    uint32_t val = 0;
    uint32_t p;

    for (p = 0; p < width; p++) {
        uint32_t px = (row[p >> 2] >> ((p & 3u) * 2u)) & 3u;

        val |= (uint32_t)colors[px] << (p * 4u);
    }

    return val;
}

/* 4bpp：GBA 4bpp tile 序——rows[4r..4r+3] 为第 r 行的 u32（低 nibble =
 * 最左像素），colors[16] 值→色号 LUT 直通（中文字库索引 0/14/15）。 */
static uint32_t blend_row_4bpp(const uint8_t *rows, uint32_t r,
                               uint32_t width, const uint8_t *colors)
{
    const uint8_t *row = &rows[r * 4u];
    uint32_t val = 0;
    uint32_t p;

    for (p = 0; p < width; p++) {
        uint32_t px = (row[p >> 1] >> ((p & 1u) * 4u)) & 0xFu;

        val |= (uint32_t)colors[px] << (p * 4u);
    }

    return val;
}

static uint32_t blend_core(uint32_t *destTile, uint32_t *spillTile,
                           const uint8_t *rows, uint32_t width,
                           uint32_t startPixel,
                           uint32_t (*expand_row)(const uint8_t *, uint32_t,
                                                  uint32_t, const uint8_t *),
                           const uint8_t *colors)
{
    const uint32_t *masks = sGlyphMasks[width][startPixel];
    const struct GlyphShiftAmount *sa = &sGlyphShiftAmounts[startPixel];
    uint32_t mask1 = masks[0] | masks[2];
    uint32_t mask2 = masks[1];
    int spill = (spillTile != 0) && (startPixel + width > 8u);
    uint32_t out1[8];
    uint32_t out2[8];
    uint32_t r;

    for (r = 0; r < 8u; r++) {
        uint32_t val = expand_row(rows, r, width, colors);

        out1[r] = (destTile[r] & mask1) | (val << sa->left);
        if (spill)
            out2[r] = (spillTile[r] & mask2) | (val >> sa->right);
    }

    destTile[0] = out1[0];
    destTile[1] = out1[1];
    destTile[2] = out1[2];
    destTile[3] = out1[3];
    destTile[4] = out1[4];
    destTile[5] = out1[5];
    destTile[6] = out1[6];
    destTile[7] = out1[7];

    if (spill) {
        spillTile[0] = out2[0];
        spillTile[1] = out2[1];
        spillTile[2] = out2[2];
        spillTile[3] = out2[3];
        spillTile[4] = out2[4];
        spillTile[5] = out2[5];
        spillTile[6] = out2[6];
        spillTile[7] = out2[7];
    }

    return (startPixel + width) / 8u;
}

uint32_t blend_glyph_1bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[2])
{
    if (width == 0u)
        return startPixel / 8u; /* 官方 Width0：无操作 */
    if (width > 8u)
        width = 8u;
    if (startPixel > 7u)
        startPixel = 7u;

    return blend_core(destTile, spillTile, rows, width, startPixel,
                      blend_row_1bpp, colors);
}

uint32_t blend_glyph_2bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[4])
{
    if (width == 0u)
        return startPixel / 8u;
    if (width > 8u)
        width = 8u;
    if (startPixel > 7u)
        startPixel = 7u;

    return blend_core(destTile, spillTile, rows, width, startPixel,
                      blend_row_2bpp, colors);
}

uint32_t blend_glyph_4bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[16])
{
    if (width == 0u)
        return startPixel / 8u;
    if (width > 8u)
        width = 8u;
    if (startPixel > 7u)
        startPixel = 7u;

    return blend_core(destTile, spillTile, rows, width, startPixel,
                      blend_row_4bpp, colors);
}
