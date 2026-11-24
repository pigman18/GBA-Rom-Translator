/* =====================================================================================
 * text_grid.h — 纯函数 tile 网格渲染器：唯一契约
 *
 * 2026-11-11 晚：串页方案（页表 / PHYS 池 / 列内容池）整体退役。
 * 回到 11-10 已实证的机制：**tile 号是屏幕行列的纯函数**，
 * 12px 跨列共享由运行时逐像素合成，不分配 tile、不抬水位、不回收。
 *
 *   row    = (CURSOR_Y + CURSOR_TILE_Y) >> 1      ; 16px 字占上下 2 tilemap 行
 *   col    = CURSOR_X + CURSOR_TILE_X             ; 8px 列（与 GetCursorTilemapPointer 同口径）
 *   tile   = TILE_BASE + 2 + (row & 7) * 62 + col*2  ; 跳过 TB/TB+1 空白对
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
 * 4bpp **低半字节 = 左像素**（scripts/font/build_chinese_font.py --nibble-order lo-first，
 * engine.py:1919），墨迹值 0/15，墨迹盒 12×12 放在 16×16 槽的 x=0..11 / y=3..14。 */
#define GRID_FONT_NORMAL    ADDR_FONT_CHS_NORMAL
#define GRID_GLYPH_BYTES    128u
#define GRID_GLYPH_SLOTS    7168u
#define GRID_INK_W          12u
#define GRID_INK_TOP        3u
#define GRID_INK_H          12u

#define GRID_PAIR_BYTES     64u   /* 一列 = 上 tile 32B + 下 tile 32B */

/* ★ 2026-11-24 BUG-12：buffered（textMode 2 / 模板 tilemap=NULL）每字占的
 * 缓冲字节数。
 *
 * 原版是 64B/字（8px 宽 × 16px 高 = 上下两片），因为原版 Small 是 8px 墨迹、
 * 8px 步进，正好一格一个字。我们的 Small 墨迹实测 9px 宽（x=0..8）、
 * 步进 10px（照火红汉化版实测：字宽 9 / 字高 10 / 步进 10），
 * 9px 墨迹在 64B 单元里放不下 —— dx>=8 的像素会被 `dx & 7` 回绕到 x=0..6，
 * 把同一个字的前几列踩掉，实机就是「血条名字区只剩碎片」。
 *
 * 扩到 128B = 16px 宽 × 16px 高（4 个 tile：上左/上右/下左/下右），
 * 才装得下 9px 墨迹 + 1px 间隙。
 *
 * 代价：名字区 0x180 字节 = 3 个 128B 单元（原 6 个 64B 单元），
 * 即最多 3 个汉字。中文物种名 3 字占绝大多数（火焰鸡/蛇纹熊/土居忍士…），
 * 更长的由 hook A 侧截断保护。
 *
 * 与火红同构：火红也是「像素直写 VRAM 缓冲」，不是 tilemap 整格映射
 * （见 docs/通用/队伍字体-火红做法调研.md §2.4 / §5）。 */
#define GRID_BUF_CELL       128u

/* tile 冲突规避用：本窗 tilemap 的扫描范围与 tile 号位宽。
 * 32×32 是 GBA 文本窗的标准表（含 0x1F0 光标槽），tile 号 10 bit。 */
#define GRID_TILEMAP_W      32u
#define GRID_TILE_BITS      1024u

/* F7 00 hi lo 的 hi 是 charmap 原始 lead（1..5/7..26/28..30），
 * 字库槽号 = lead_adjust(hi)*256 + lo（scripts/font/build_chinese_font.py::glyph_index）。
 * 实证：最终 ROM 里 160,998 个 F7 token 的 hi 分布含 28/29/30，
 * 而槽号 hi 上界只有 27 ⇒ 绝不能把 (hi,lo) 直接当槽号。 */
#define GRID_LEAD_ADJUST(h) \
    ((unsigned)(h) - 1u - (((unsigned)(h) >= 6u) ? 1u : 0u) \
                       - (((unsigned)(h) >= 0x1Bu) ? 1u : 0u))

#endif /* TEXT_GRID_H */
