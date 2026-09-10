/* ============================================================================
 * tile_alloc.h — v9 队列 tile 分配器接口（2026-09-09）
 *
 * 取代 v8 的「扫描 VRAM 找空位」模型（活引用位图 + VRAM 非空 + ours 段表）。
 * 新模型：**每个 win 维护一条队列**。
 *
 *   队列 = 本窗可分配的连续 tile 区间 [head, end)
 *          head = win[0x16] TILE_BASE（0 号槽官方空白，跳过）
 *          end  = 本窗 charBlock 上界（仅 OBJ 物理隔离）
 *   游标 = 队列内下一个可分配位置；切换窗 → 置首
 *   消费 = ① 主动文本分配 v8_alloc_tile  ② UI 分配 v8_ui_alloc
 *          两者共用同一游标，领到即占用，单调前进
 *
 * 铁律：
 *   ① 确定性：纯游标推进，同调用序列 → 同 tile 号（无随机、无环境依赖）。
 *   ② 零扫描：不读 tilemap、不读 screenblock、不做 VRAM 非空校验。
 *   ③ 宁缺不砸：队列耗尽返回 0，调用方放弃绘制。
 *
 * 实现见 src/text/tile_alloc.c。
 * ==========================================================================*/
#ifndef TILE_ALLOC_H
#define TILE_ALLOC_H

#include <stdint.h>
#include "game.h"

/* 打印块边界（InitTextPrinter 调用）。
 * 仅：① 归属 win 变化 → 重建队列并把游标置首；② 复位 12px 相位。
 * 同一 win 的后续文本块不重置游标，接着队列往后排。 */
void v8_alloc_begin(TextPrinter *win);

/* ① 主动文本分配：领连续 glyph_len 个 tile（相对 charBase 号）。
 * 失败（队列耗尽）→ 返回 0，调用方放弃。 */
uint16_t v8_alloc_tile(TextPrinter *win, uint8_t font_px, uint8_t glyph_len);

/* ② UI 分配：图集 / 窗框等 UI 占位领 n 个 tile。
 * 与文本分配共用同一队列游标 —— UI 先领则文字排在 UI 之后。 */
uint16_t v8_ui_alloc(TextPrinter *win, uint16_t n);

/* 当前队列游标（调试/埋点用）。 */
uint16_t v8_queue_cursor(void);

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

/* 显式复位行相位（渲染层在换行控制码 FA/FB/FE 上直调）。
 *
 * 为什么需要「显式」：v8_phase_get 的行标识（tpl^curY^curTileY）是**间接**检测，
 * 依赖引擎在取下一行首字之前就把 curY/curTileY 推到位。官方 FE 的时序是
 * 「先推一个、另一个稍后才变」（见 v8_phase_get 注释），存在窗口；
 * 一旦漏检，下一行首字会带着上一行的累计相位起步 ——
 * 累计相位 = 12n mod 8，**n 为奇数时 = 4**，于是走 phase!=0 分支复用
 * v8_phase_last_tile()（= 上一行行尾字的尾列 tile）⇒ 覆写行尾字右半
 * ⇒ 实机「奇数个字的一行，换行后行尾只剩半个字」。
 * 本函数不依赖时序、由渲染层在换行码上直接调用，是那条链的兜底。 */
void v8_phase_reset(void);

#endif /* TILE_ALLOC_H */
