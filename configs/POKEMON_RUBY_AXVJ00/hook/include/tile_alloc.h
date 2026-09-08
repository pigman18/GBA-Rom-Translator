/* ============================================================================
 * tile_alloc.h — v8 顺序 tile 分配器接口（2026-09-04）
 *
 * 取代 v6 静态行带表 + v7 动态行基址表的第三套方案，回到用户最初认知的
 * 「顺序放入 + 避让带」模型。一个字的 tile 号只有一个来源：本顺序分配器。
 *
 * 三条铁律：
 *   ① 确定性：固定起点遍历跳过占用，同输入 → 同输出（防 v4 随机取址坑）。
 *   ② 权威性：避让带来自 tilemap 活引用扫描，不靠猜（漏一个就砸官方字）。
 *   ③ 隔离性：charBase 物理分块天然隔离 OBJ 精灵区（上界用 REG_DISPCNT 截断）。
 *
 * 实现见 src/text/tile_alloc.c。
 * ==========================================================================*/
#ifndef TILE_ALLOC_H
#define TILE_ALLOC_H

#include <stdint.h>
#include "game.h"

/* 打印会话开始时快照一次占用位图 + 复位游标与相位（InitTextPrinter 块边界调用）。
 * 之后本轮所有中文查这张快照，不看自己刚写入的表项 → 防自画污染。
 * 同时把分配游标与 12px 相位一并复位——三者同生命周期，窗口切换自然从头来。 */
void v8_alloc_begin(TextPrinter *win);

/* 领一块连续 glyph_len 个 tile 的相对 charBase 偏移号（0~1023）。
 * 确定性：从空闲带起点 + 游标遍历，跳过占用位图，取首个连续 glyph_len 空闲。
 * 无空闲 → 回卷到起点再扫，仍无 → 返回 0（调用方放弃，宁缺不砸 UI）。 */
uint16_t v8_alloc_tile(TextPrinter *win, uint8_t font_px, uint8_t glyph_len);

/* ---- 12px 相位（按行隔离，单变量 + 行标识）----
 * 相位是「行内像素游标」px（phase = px & 7），属于一行而非一个窗口/文本块。
 * 用单一变量 ADDR_V8_PHASE + 行标识 ADDR_V8_PHASE_ROW（tpl^curY）表达：
 *   同一行（行标识匹配）→ 相位续接（跨文本块「类型」→「8」紧排）；
 *   换行 / 换窗口（行标识变化）→ 相位归零（新行从头画，杜绝跨窗口残留）。
 * 不再用全局 8 槽 + 行指纹 key 的复杂状态表。 */

/* 取当前行内相位 px（内部先按 win 校验行标识，失配即归零）。phase = px & 7。 */
uint16_t v8_phase_get(TextPrinter *win);

/* 推进相位 px += adv（adv = 本字步进像素）。 */
void v8_phase_advance(uint16_t adv);

/* 当前行「上一列已领 tile 号」（phase!=0 时复用该列）。 */
uint16_t v8_phase_last_tile(void);
void v8_phase_set_last_tile(uint16_t tile);

#endif /* TILE_ALLOC_H */
