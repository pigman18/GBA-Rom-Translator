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

/* ---- 12px 相位（R1-A 零状态化：渲染层唯一可变状态 = px 游标）----
 * 相位是「行内像素游标」px（phase = px & 7），唯一存储 = ADDR_V8_PHASE（EWRAM）。
 * 2026-09-23 起删除行标识 ADDR_V8_PHASE_ROW 与尾列 ADDR_V8_LAST_TILE 两个
 * 存储变量（对标 Tonc TTE 的唯一 cursorX）：
 *   换行 / 换窗口归零只由两条**显式**边界承担 ——
 *     ① InitTextPrinter 块边界 → v8_alloc_begin 复位；
 *     ② FA/FB/FE 换行类控制码 → v8_phase_reset（渲染层在 Origin 尾调前直调）。
 * 旧行指纹是间接检测，依赖引擎先推 curY/curTileY，存在漏检窗口
 * （见 git 历史 v8_phase_get 注释），已随本变量一并退役。 */

/* 取当前行内相位 px（R1-A：直接读 px 游标，无行标识检测）。phase = px & 7。 */
uint16_t v8_phase_get(TextPrinter *win);

/* 推进相位 px += adv（adv = 本字步进像素）。 */
void v8_phase_advance(uint16_t adv);

/* 当前行行尾列 tile —— R1-A 起为纯算推导（不存状态）：
 * 尾列 = 上一字 t1 对，而分配游标语义恰是「上一成功领号的后沿」
 * ⇒ tail = CURSOR - 2（前提：phase!=0 ⇒ 上字必领过 t1，ink≥8 可证）。
 * 三类兜底返回 0 ⇒ 调用方领新对：
 *   ① 队列换主（win+tpl 变化，绝不跨窗复用别家 tile）；
 *   ② 游标未出 lo+2（本会话尚无领号）；
 *   ③ 上字 t1 领号失败（w1 被裁 0）⇒ 游标停在 t0 对后沿 ⇒ 返回 t0，
 *      与旧「last = (w1 ? t1 : t0)」语义逐位一致。 */
uint16_t v8_phase_last_tile(TextPrinter *win);

/* 显式复位行相位（渲染层在换行控制码 FA/FB/FE 上直调）。
 * R1-A 后它是「换行不带 InitTextPrinter」场景的唯一归零点（行指纹已退役），
 * 与 ① 块边界 v8_alloc_begin 复位共同覆盖全部行/窗切换；
 * 不依赖引擎先推 curY/curTileY 的时序（旧指纹漏检窗口即由此而来）。
 * 只清「行内 px 游标」；**不动分配游标**（游标跨行继续推进，
 * 正是为了让下一行的 tile 不与上一行重叠）。 */
void v8_phase_reset(void);

#endif /* TILE_ALLOC_H */
