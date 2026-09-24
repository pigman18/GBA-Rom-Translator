/* ============================================================================
 * diag_log.h — 只读字形落点追踪（**默认关闭**）
 *
 * 目的（2026-09-21）：
 *   当前**没有数据**回答的问题 —— 两个窗口的 tile 号为什么会撞？
 *   号 = `TILE_BASE + block_base(CUR_X,CUR_Y) + TILE_OFFSET`，
 *   要判定「谁和谁撞」，必须拿到每个字形落笔时的：
 *     win / tpl / tpl[TILEMAP] / tpl[TILE_DATA] / TILE_BASE / TILE_OFFSET
 *     CUR_X / CUR_Y / CURSOR_TILE_X / CURSOR_TILE_Y / 最终 t0 / 相位
 *
 * 🔴 本模块**只写自己的采样块**（EWRAM 0x0203C000 起 8 KB，实测全零空闲），
 *    不碰 VRAM / tilemap / 引擎字段 ⇒ 对画面零影响。
 * 🔴 交付版必须把 `CHS_TRACE` 置 0（关掉调用点，同时本模块变成空壳）。
 * ==========================================================================*/
#ifndef DIAG_LOG_H
#define DIAG_LOG_H

/* 诊断开关：1 = 记录（会往 EWRAM 写，仅供 dump 分析）；0 = 完全无副作用 */
#define CHS_TRACE 1

#include <stdint.h>

/* 采样块基址（EWRAM）。用 mgba_drive --dump 取 ewram，偏移 = 0x1C000。
 *
 * 布局（单位 u32）：
 *   w0        magic 'ADX2'
 *   w1        glyph_calls     字形落砖总调用数
 *   w2        ring filled     环形已写入的「不同」记录数
 *   w3        win_uniq        不同 win 实例数
 *   w4        dup             被去重（与上一条完全相同）的次数
 *   w5..w7    保留
 *   w8..w199  窗口表 24 × {win, tpl, tileData, map, count, 0,0,0}
 *   w200..    环形 369 × 5 字
 *              {win,
 *               cx | cy<<8 | ctx<<16 | cty<<24,
 *               tb | off<<12 | prev<<16,      ← prev = v26 反查到的「上一字 R 砖号」
 *               t0 | t1<<16,
 *               phase | adv<<8 | tm<<16 | ch<<24}
 */
#define ADDR_TRACE            0x0203C000u
#define TRACE_BYTES           8192u

#if CHS_TRACE
void trace_glyph(uint32_t win, uint32_t tpl, uint16_t tb, uint16_t off,
                 uint8_t cx, uint8_t cy, uint8_t ctx, uint8_t cty,
                 uint16_t t0, uint16_t t1, uint16_t prev,
                 uint8_t phase, uint8_t adv,
                 uint8_t tm, uint8_t ch);
#endif

#endif /* DIAG_LOG_H */
