/* ============================================================================
 * tile_alloc.h — v7 动态 tile 分配器接口（2026-09-04）
 *
 * 与 v6 静态选址（scene_cfg.c 行带基址表）并行：静态表优先，未命中才走
 * 本动态算法。动态算法 = 运行时读 tilemap 活引用 → 快照占用位图 → 确定性
 * 遍历 charBase 空闲带跳过占用领 tile。
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

/* 打印会话开始时快照一次占用位图（InitTextPrinter 块边界调用）。
 * 之后本轮所有中文查这张快照，不看自己刚写入的表项 → 防自画污染。 */
void v7_alloc_begin(TextPrinter *win);

/* 领一块连续 2 tile（t 与 t+1）的相对 charBase 偏移号（0~1023）。
 * 确定性：从空闲带起点遍历，跳过占用位图，取首个连续 2 空闲。
 * 无空闲 → 回卷到起点（宁部分不显示也不砸 UI）。 */
uint16_t v7_alloc_tile(TextPrinter *win);

#endif /* TILE_ALLOC_H */
