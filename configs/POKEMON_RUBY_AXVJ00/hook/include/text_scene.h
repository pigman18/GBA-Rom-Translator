/* text_scene.h — 缓冲打印机 + 最小 remap；绘制政策在 text_render */
#ifndef TEXT_SCENE_H
#define TEXT_SCENE_H

#include "game.h"

/* 序言跳板 → ROM PrintNextChar@0x08003300（entry.s）；非数据表 */
int PrintNextChar_Origin(TextPrinter *win);

int scene_is_buffer_printer(TextPrinter *win);
int scene_delegate_buffer_print(TextPrinter *win);
int scene_jp_via_chs(TextPrinter *win);

uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile);

/* 落址策略（text_render.c 消费）：
 *   scene_should_use_linear → 1=线性池公式（tm0/战斗/商店行），0=Mode2 栅格
 *   scene_apply_linear_floor → 行首把 TILE_OFFSET 抬到该场景地板（避让 UI 图标段）
 *   scene_gctn_linear        → TILE_BASE + TILE_OFFSET + 2*xOff + yOff
 *   scene_gctn_mode2         → (CX+tile_x, CY+TY) 栅格 + band/origin */
int scene_should_use_linear(TextPrinter *win, uint8_t write_op);
void scene_apply_linear_floor(TextPrinter *win);
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff);
void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower);

#endif /* TEXT_SCENE_H */
