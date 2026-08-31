/* ============================================================================
 * blend_glyph.h — 混合写入像素原语（新文本渲染层 v5 唯一绘制原语）
 *
 * 架构不变量（docs/REWRITE_DESIGN_混合写入架构.md §4.1）：
 *   - 运行时零 tile 分配：字形像素经 RMW 混合写入窗口 tileData，
 *     tile 无所有权；跨列共享是原语内置能力；
 *   - 游标推进唯一依据 = 返回值 (startPixel + width) / 8（列数）；
 *   - 纯函数、零全局状态 ⇒ 可离线单测（tests/test_blend_glyph.py 对拍）。
 *
 * 语义照抄官方 pokeruby text.c DrawGlyphTile_UnshadowedFont（vendored 副本
 * reference/pokeruby/draw_glyph_tile.c，含 sGlyphMasks 边角语义）：
 *   - 首 tile：跨度 [startPixel, startPixel+width) 内整段重写（字形 0 号色 =
 *     colors[0]，官方同款"跨度内清底"）；跨度外像素逐位保留；
 *   - 溢出：startPixel+width>8 时超出部分 OR 进 spillTile（纯 OR，不清底、
 *     spill 跨度外像素保留——与官方掩码表逐位一致）；
 *   - 返回值恒为 (startPixel + width) / 8（含无溢出 0 列的情况）。
 *
 * spillTile 必须由调用方给出（2026-08-31 定案，设计稿 §4.3 已同步修订）：
 * 官方 mode0 窗口 tileData 的物理右邻 = +64B（+16 u32），mode2 血条缓冲
 * 右邻 = +32B（+8 u32）——右邻距离随布局不同，不能硬编码在原语里。
 * 无溢出或调用方不打算写溢出时传 0；返回值照常。
 *
 * 像素序约定（GBA 4bpp tile：每 u32 一行 8 像素，低 nibble = 最左像素）：
 *   1bpp：rows = 8 字节，bit7 = 每行最左像素（官方 unshadowed 字模序）；
 *   2bpp：rows = 16 字节，GBA 2bpp 序——每字节低 2 位 = 最左像素；
 *         colors[4] 为值→色号 LUT 直通（0 建议映射 bg，描边/前景按字库实际）；
 *   4bpp：rows = 32 字节，GBA 4bpp tile 序——每 u32 一行 8 像素，低 nibble =
 *         每行最左像素；colors[16] 为值→色号 LUT 直通（中文字库索引 0=底色/
 *         14=阴影/15=前景，调用方构造 colors[0]=bg,colors[14]=shadow,
 *         colors[15]=fg，其余项可任意）。
 * ==========================================================================*/
#ifndef BLEND_GLYPH_H
#define BLEND_GLYPH_H

#include <stdint.h>

uint32_t blend_glyph_1bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[2] /* {bg, fg} */);

uint32_t blend_glyph_2bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows /* 16B */,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[4] /* 值→色号 LUT */);

uint32_t blend_glyph_4bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows /* 32B，GBA 4bpp tile */,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[16] /* 值→色号 LUT 直通 */);

/* 12px 步进辅助（2026-08-31 新增，纯函数、零状态 ⇒ 可单测）：
 * 从 128B 中文字模槽（16x16，[TL@0][BL@32][TR@64][BR@96]）取出字列
 * [xs, xs+w)，拼成**连续**的两块 4bpp tile：up=上半 8 行、lo=下半 8 行，
 * 各 32B，不足 8 列的部分右侧补 0（值 0 = 底色）。
 *
 * 存在意义：blend 原语一次最多写 8 像素宽，且**不支持 src 列偏移**
 * （blend_row_4bpp 固定从 src 第 0 像素取）。12px 字在 phase!=0 时，
 * 待写的一个输出块会同时横跨 TL(列4-7) 与 TR(列0-3) 两个源 tile，
 * 必须先拼成连续块再交给 blend。
 *
 * w 会钳到 8；xs+j >= 16 的越界列按 0 处理（墨迹实宽 12，正常不会触发）。 */
void extract_cols(const uint8_t *g128, uint32_t xs, uint32_t w,
                  uint8_t up[32], uint8_t lo[32]);

#endif /* BLEND_GLYPH_H */
