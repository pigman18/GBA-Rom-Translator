/*
 * TODO(未验�?: 未挂 main.asm�? * 旧逻辑：attr==WINDOW_WIDTH �?font==3 �?language�?0 时宽度�?（ARM 钩子）�? * 对应：GetWindowAttribute @ 0x0800414C
 */
#include "game.h"

#define WINDOW_WIDTH 1u /* 与旧 asm 比较用；JP 枚举待核 */

uint32_t GetWindowAttribute_Chinese(TextPrinter *win, uint32_t attr, uint32_t raw_width)
{
    if (attr != WINDOW_WIDTH)
        return raw_width;
    if (win_u8(win, WIN_FONTNUM) != 3)
        return raw_width;
    /* language 字段偏移待核（旧 asm �?win+2�?*/
    uint8_t lang = win[2];
    if (lang > 30)
        return raw_width;
    return (uint32_t)lang * 2u;
}
