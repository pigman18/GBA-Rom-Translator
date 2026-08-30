#ifndef GUARD_TILE_ALLOC_H
#define GUARD_TILE_ALLOC_H

#include "game.h"

/* tm1 未登记窗口的中文行 tile 分配（详见 src/text/tile_alloc.c 头注）。
 * 在 chs_blit 的未登记分支调用；登记窗口（PTR/DYN 分区）不得调用。 */
void tile_alloc_tm1_row(TextPrinter *win);

#endif
