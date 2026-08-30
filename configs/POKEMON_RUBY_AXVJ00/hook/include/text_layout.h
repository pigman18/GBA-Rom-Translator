/* ============================================================================
 * text_layout.h — 窗口落址**算法**：查表、求值、分区选择、槽查询、落址
 *
 * ── 分层（2026-08-30 重构，与 bak/text-v3 的历史切法一致）──────────────
 *   include/text_scene.h  + src/text/text_scene.c  = **数据**：结构体定义 +
 *                          每个窗口一条的静态配置（kOptWindow 等）。
 *                          ⚠ 该文件是**纯数据文件，一个函数都没有**。
 *   include/text_layout.h + src/text/text_layout.c = **算法**：本文件声明的
 *                          全部函数（查表、求值、分区选择、槽查询、落址）。
 *
 *   新增窗口只改 text_scene.c + 登记进 kWindows[]，算法侧不用动。
 *
 * 接口形状沿用 bak/text_original/text_scene.h 的同名同签名：
 *   text_render.c / PrintNextChar_hook.c 依赖本文件即可，不需要碰配置数据。
 * ==========================================================================*/
#ifndef TEXT_LAYOUT_H
#define TEXT_LAYOUT_H

#include "text_scene.h"     /* struct WinCfg / Tm1Zone / TileRemap / Mode2Region */

/* ---- 登记查表 ------------------------------------------------------------
 * 按模板地址查表；未登记返回 NULL（调用方走官方字段兜底，不猜场景）。 */
const struct WinCfg *scene_lookup(uint32_t tpl);

/* ---- 与 bak/text_original 同名同签名的 scene 接口（渲染层唯一依赖）------*/
int  PrintNextChar_Origin(TextPrinter *win);   /* entry.s 跳板 → ROM 0x08003300 */
int  scene_is_buffer_printer(TextPrinter *win);
int  scene_delegate_buffer_print(TextPrinter *win);
int  scene_should_use_linear(TextPrinter *win, uint8_t write_op);
void scene_apply_linear_floor(TextPrinter *win);
uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile);
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff);
void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower);

/* ---- PTR/DYN 的 per-glyph 接入点（text_render.c 于每字开头调用一次）-----
 * note_glyph：做 zone_select（PTR → 绑定该字槽表项；DYN → 记录 off/span）。
 * is_ptr_mode：本字是否 PTR（渲染层据此用 16px 步进）。 */
void scene_note_glyph(TextPrinter *win, uint16_t glyph_id);
uint8_t scene_is_ptr_mode(TextPrinter *win);

#endif /* TEXT_LAYOUT_H */
