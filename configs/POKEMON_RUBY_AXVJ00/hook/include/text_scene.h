/* text_scene.h — 布局特例（战斗/商店/PSS/底栏）；其余跟原生 tm/font */
#ifndef TEXT_SCENE_H
#define TEXT_SCENE_H

#include "game.h"

extern const uint8_t PrintNextChar_Origin[];

int scene_is_buffer_printer(TextPrinter *win);
int scene_delegate_buffer_print(TextPrinter *win);
int scene_jp_via_chs(TextPrinter *win);

int scene_should_use_linear(TextPrinter *win, uint8_t write_op);
void scene_apply_linear_floor(TextPrinter *win);
uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile);
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff);
void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower);

#endif /* TEXT_SCENE_H */
