/* text_scene.h — 场景布局门控（docs/SCENE_GATES_AXVJ.md） */
#ifndef TEXT_SCENE_H
#define TEXT_SCENE_H

#include "game.h"

/* 原生 PrintNextChar@0x080032F8 副本（entry.s incbin 0xA0） */
extern const uint8_t PrintNextChar_Origin[];

/* ---- Layer A：路由 ---- */
int scene_is_buffer_printer(TextPrinter *win);
int scene_delegate_buffer_print(TextPrinter *win);
int scene_is_battle_interface_dest(TextPrinter *win);
int scene_jp_via_chs(TextPrinter *win);

/* ---- Layer B：探测器 ---- */
int scene_is_party_footer(TextPrinter *win);
int scene_field_wants_linear(TextPrinter *win);
int scene_menu_wants_mode2(TextPrinter *win);
int scene_is_shop_desc(TextPrinter *win);
int scene_is_shop_bag_list(TextPrinter *win);
int scene_is_battle_text_window(TextPrinter *win);
int scene_battle_force_linear(TextPrinter *win);

/* ---- Layer B：布局效应 ---- */
int scene_should_use_linear(TextPrinter *win, uint8_t write_op);
void scene_mode2_apply(TextPrinter *win, int *x, int *y, int *band, int *origin);
void scene_apply_linear_floor(TextPrinter *win);
uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile);
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff);
void scene_gctn_mode2(TextPrinter *win, int tile_x, uint16_t *upper, uint16_t *lower);

int scene_keep_linear_16(TextPrinter *win);

#endif /* TEXT_SCENE_H */
