/* ============================================================================
 * chinese_glyph.c — pokeE 式 1bpp 位流 → 128B 4bpp 字形单元（运行时转换）
 *
 * 地基更换（2026-09-08 用户拍板）：字库存储从 4bpp 预渲染（128B/字）换成
 * pokeE 1bpp 位流（16B/11B 每字，ROM 省 8 倍），渲染时逐字转换。
 *
 * 位流格式（pokeE Convert1bppTo2bpp 反汇编钉死）：
 *   每行 width 位 MSB-first 连续排布，行间无填充，共 rows 行；
 *   大库 11 行×11bit→16B 步进、渲染行偏移 1；小库 9 行×9bit→11B 步进、偏移 2。
 * 输出单元与 4bpp 库布局一致：TL@0 / BL@0x20 / TR@0x40 / BR@0x60，
 * 每 tile 8 行×4B，每 u32 一行 8 像素、低 nibble = 最左像素。
 * 上色：墨迹→15（fill_colors 映射 C），右下阴影(+1,+1、重叠去除)→14（E），
 *       空→0（D 底色）。
 * 纯函数零状态（pokeE 的 EWRAM 三缓冲 0x0203FF40 方案弃用——直接算进调用方
 * 栈上单元，与全工程「栈上暂存」惯例一致）。
 * ==========================================================================*/
#include "text.h"

void chs_cell_from_1bpp(const uint8_t *bits, uint32_t width, uint32_t rows,
                        uint32_t line_off, uint8_t cell[CHS_CELL_BYTES])
{
    uint8_t ink[16][2]; /* 16×16 墨迹位图：ink[y][0]=左8列、[1]=右8列，bit0=最左 */
    unsigned r, x, half;

    for (r = 0; r < 16u; r++) {
        ink[r][0] = 0u;
        ink[r][1] = 0u;
    }
    for (r = 0; r < rows && line_off + r < 16u; r++) {
        uint32_t base = r * width;
        uint32_t lo = 0u, hi = 0u;

        for (x = 0; x < width; x++) {
            uint32_t bi = base + x;
            uint32_t bit = (bits[bi >> 3] >> (7u - (bi & 7u))) & 1u;

            if (x < 8u) {
                if (bit)
                    lo |= 1u << x;
            } else if (bit) {
                hi |= 1u << (x - 8u);
            }
        }
        ink[line_off + r][0] = (uint8_t)lo;
        ink[line_off + r][1] = (uint8_t)hi;
    }

    for (r = 0; r < 16u; r++) {
        for (half = 0; half < 2u; half++) {
            uint8_t b[4] = {0u, 0u, 0u, 0u};

            for (x = 0; x < 8u; x++) {
                unsigned gx = half * 8u + x;
                uint32_t v;

                if (ink[r][half] & (uint8_t)(1u << x)) {
                    v = 15u; /* 墨 */
                } else if (r >= 1u && gx >= 1u &&
                           (ink[r - 1u][(gx - 1u) >> 3] & (uint8_t)(1u << ((gx - 1u) & 7u)))) {
                    v = 14u; /* 右下阴影（左上邻有墨、本格空） */
                } else {
                    v = 0u;
                }
                b[x >> 1] |= (uint8_t)(v << ((x & 1u) ? 4u : 0u));
            }
            {
                uint8_t *q = cell
                    + (half ? (r < 8u ? 0x40u : 0x60u) : (r < 8u ? 0x00u : 0x20u))
                    + (r & 7u) * 4u;
                q[0] = b[0];
                q[1] = b[1];
                q[2] = b[2];
                q[3] = b[3];
            }
        }
    }
}
