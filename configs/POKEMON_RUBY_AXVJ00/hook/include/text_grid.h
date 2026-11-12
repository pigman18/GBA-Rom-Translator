/* =====================================================================================
 * text_grid.h — 纯函数 tile 网格渲染器：唯一契约
 *
 * 2026-11-11 晚：串页方案（页表 / PHYS 池 / 列内容池）整体退役。
 * 回到 11-10 已实证的机制：**tile 号是屏幕行列的纯函数**，
 * 12px 跨列共享由运行时逐像素合成，不分配 tile、不抬水位、不回收。
 *
 *   row    = (CURSOR_Y + CURSOR_TILE_Y) >> 1      ; 16px 字占上下 2 tilemap 行
 *   col    = CURSOR_X + CURSOR_TILE_X             ; 8px 列（与 GetCursorTilemapPointer 同口径）
 *   tile   = TILE_BASE + (row & 7) * 62 + col*2   ; upper, lower = upper+1
 *
 * 依据：
 *  - docs/POKEMON_RUBY_AXVJ00.md §9.3.3：tm1 的 [TB, TB+512) 是预载的
 *    256 个 8×16 日文字库槽；汉化后这些槽被中文按屏幕列接管，
 *    池与原版同量，**不需要扩容 charBase**。
 *  - TASKS.md §1.2（2026-11-10）：上述公式「纯函数、无累加器、无场景策略」。
 *  - §9.3.5：62 tile/行 × 8 行 = 496，尾部 496..511 留给 ▶ 光标；
 *    行宽写死 30 / 只用 CTY 算行 / 漏加 CURSOR_TILE_X 均已证伪。
 *
 * 12px 相位不再靠 EWRAM 状态：从串首（或最近换行）到当前字节，按
 * F7=12px / PCS=8px / 控制码=0px 累计像素，phase = w & 7 ∈ {0,4}。
 * 字的墨迹盒覆盖 (col..col+1) 两列，盒内清 0 再写墨迹，
 * 共享列的前 4px 天然落在盒外 → 不会被邻字擦掉。
 * ===================================================================================== */
#ifndef TEXT_GRID_H
#define TEXT_GRID_H

#include "game.h"

/* 一行段 62 个 tile = 31 列（每列 2 tile）；8 段 = 496 tile = 0x1F0。
 * 0x1F0/0x1F1 是菜单 ▶ 固定 tile 对，0x1E8..0x1FB 是 Summary 提示图标，
 * 0x1FC..0x1FF 是图鉴编号/精灵球图标 —— 网格尾部不越过 0x1F0。 */
#define GRID_SEG_TILES      62u
#define GRID_SEG_COUNT      8u
#define GRID_COLS_PER_SEG   (GRID_SEG_TILES / 2u)   /* 31 列 */
#define GRID_TILE_LIMIT     0x1F0u                  /* 不写 >= 0x1F0 的 tile */

/* 字库：0x09000000 起 7168 槽 × 128B，顺序 TL(0) BL(32) TR(64) BR(96)，
 * 4bpp **低半字节 = 左像素**（scripts/build_chinese_font.py --nibble-order lo-first，
 * engine.py:1919），墨迹值 0/15，墨迹盒 12×12 放在 16×16 槽的 x=0..11 / y=3..14。 */
#define GRID_FONT_NORMAL    ADDR_FONT_CHS_NORMAL
#define GRID_GLYPH_BYTES    128u
#define GRID_GLYPH_SLOTS    7168u
#define GRID_INK_W          12u
#define GRID_INK_TOP        3u
#define GRID_INK_H          12u

#define GRID_PAIR_BYTES     64u   /* 一列 = 上 tile 32B + 下 tile 32B */

/* F7 00 hi lo 的 hi 是 charmap 原始 lead（1..5/7..26/28..30），
 * 字库槽号 = lead_adjust(hi)*256 + lo（scripts/build_chinese_font.py::glyph_index）。
 * 实证：最终 ROM 里 160,998 个 F7 token 的 hi 分布含 28/29/30，
 * 而槽号 hi 上界只有 27 ⇒ 绝不能把 (hi,lo) 直接当槽号。 */
#define GRID_LEAD_ADJUST(h) \
    ((unsigned)(h) - 1u - (((unsigned)(h) >= 6u) ? 1u : 0u) \
                       - (((unsigned)(h) >= 0x1Bu) ? 1u : 0u))

#endif /* TEXT_GRID_H */
