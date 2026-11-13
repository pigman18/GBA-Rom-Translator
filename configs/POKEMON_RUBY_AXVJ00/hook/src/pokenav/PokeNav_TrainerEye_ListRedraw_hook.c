/* PokeNav_TrainerEye_ListRedraw_hook — 列表重画前清右栏残墨。
 *
 * bot 帧 153–163（详情 B 退回列表）：origin 右栏无饱和红，translated 有
 * ~196px，差分图为详情红标签「作/持/自/可梦」残留。中文 12px 不能像
 * 日文 8px 整列盖住详情字；退回时 ListRedraw 只 InitWin+重印，不清 VRAM。
 *
 * 本钩在进原版 EBD2C 前 Blank 窗 0x2F (13,2)–(28,15)（与 P33 进详情同矩形）。
 * 与红条 TitleBlit / 开始菜单无关（开始菜单内侧饱和红 only_T=0）。
 */
#include "game.h"

typedef void (*menu_blank_t)(uint32_t left, uint32_t top, uint32_t right,
                             uint32_t bottom);
typedef void (*init_win_t)(uint32_t window_id);

#define ADDR_INIT_MENU_WINDOW 0x0806F158u

#define LIST_WIN 0x2Fu
#define RIGHT_L  13u
#define RIGHT_T  2u
#define RIGHT_R  28u
#define RIGHT_B  15u

void PokeNav_TrainerEye_ListBlank_C(void)
{
    uint8_t *flag = (uint8_t *)(uintptr_t)ADDR_TE_LIST_NEED_BLANK;
    menu_blank_t blank = (menu_blank_t)(ADDR_MENU_BLANK_WINDOW_RECT | 1u);
    init_win_t init = (init_win_t)(ADDR_INIT_MENU_WINDOW | 1u);

    /* 仅详情退回置位；平常滚动 ListRedraw 不能 Blank（会洗掉未重印行） */
    if (*flag == 0u)
        return;
    *flag = 0u;
    init(LIST_WIN);
    blank(RIGHT_L, RIGHT_T, RIGHT_R, RIGHT_B);
}
