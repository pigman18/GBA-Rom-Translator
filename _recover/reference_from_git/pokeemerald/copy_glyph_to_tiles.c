/* =====================================================================================
 * copy_glyph_to_tiles.c — reference vendored primitive（pret/pokeemerald）
 *
 * source  : GLYPH_COPY              tools/pokeemerald/src/text.c L583-609
 *           FillBitmapRect4Bit      tools/pokeemerald/src/blit.c L73
 * fetched : 本地 clone tools/pokeemerald @ master, 2026-08（diff 同步以该镜像为准）
 * 改写    : 仅 (a) gWindows/gCurGlyph 等全局 → 显式参数；(b) ref_ 前缀/static 化。
 * 契约    : ref_glyph_copy 吃「行主序 nibble 流」——每行 u32 数组步进，
 *           行距 = winStrideBytes；x/y 为窗内像素坐标，(j/8)*32 即跨 tile 列寻址。
 * 地位    : draw_tile（text_render.c）的官方对照参照，runtime 不切换（2026-08-27 定案）。
 * 契约发现：GLYPH_COPY 假设行流为 DecompressGlyphTile 生成的 swap-packed 格式
 *           （每字节左右互换、LSB 先消费），与本工程 CopyGlyph2bppTo4bpp_Origin
 *           输出的标准 tile 序不同构；直接接入需连上游解码器语义一并搬。
 *           另日版 tm1 等宽窗目标列槽物理不连续，连续视图假设不成立。
 *           故按用户决策维持现役三段循环实现。
 * ===================================================================================== */
#include "../../include/text_render.h"

/* ---- GLYPH_COPY verbatim 数学（upstream 内联于 CopyGlyphToWindow）----
 * 只写非零 nibble（墨迹 OR 入底图），背景由调用方先填充
 * （Emerald 分工：ClearTextSpan/FillBitmapRect4Bit 负责清底）。 */
void ref_glyph_copy(uint8_t *windowTiles, uint32_t winStrideBytes,
                    uint32_t x, uint32_t y,
                    const uint32_t *glyphPixels, int32_t width, int32_t height)
{
    uint32_t xAdd, yAdd, pixelData, bits, toOrr;
    uint8_t *dst;
    uint32_t i = y, j;

    xAdd = x + width;
    yAdd = y + height;
    for (; i < yAdd; i++)
    {
        pixelData = *glyphPixels++;
        for (j = x; j < xAdd; j++)
        {
            if ((toOrr = pixelData & 0xF))
            {
                dst = windowTiles + ((j / 8) * 32) + ((j % 8) / 2)
                    + ((i / 8) * winStrideBytes) + ((i % 8) * 4);
                bits = ((j & 1) * 4);
                *dst = (uint8_t)((toOrr << bits) | (*dst & (0xF0 >> bits)));
            }
            pixelData >>= 4;
        }
    }
}

/* ---- FillBitmapRect4Bit 参数化版：tile 面上的 4bpp 矩形填色 ---- */
void ref_fill_rect4bit(uint8_t *windowTiles, uint32_t winStrideBytes,
                       uint32_t x, uint32_t y,
                       int32_t width, int32_t height, uint8_t fillValue)
{
    uint32_t xEnd = x + (uint32_t)width;
    uint32_t yEnd = y + (uint32_t)height;
    uint32_t loopX, loopY;
    uint8_t toOrr1 = (uint8_t)(fillValue << 4);
    uint8_t toOrr2 = (uint8_t)(fillValue & 0xF);

    for (loopY = y; loopY < yEnd; loopY++)
    {
        for (loopX = x; loopX < xEnd; loopX++)
        {
            uint8_t *pixels = windowTiles + ((loopX >> 1) & 3) + ((loopX >> 3) << 5)
                            + ((loopY >> 3) * winStrideBytes) + ((loopY & 7) * 4);
            if (loopX & 1u)
                *pixels = (uint8_t)(toOrr1 | (*pixels & 0xF));
            else
                *pixels = (uint8_t)(toOrr2 | (*pixels & 0xF0));
        }
    }
}
