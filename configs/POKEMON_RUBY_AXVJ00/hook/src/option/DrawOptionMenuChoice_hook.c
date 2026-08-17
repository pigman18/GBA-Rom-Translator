/* DrawOptionMenuChoice_hook — 设置窗口选项高亮绘制。
 *
 * JP 原版文本为 FC 05 0F <正文>，dst[2] 就是颜色前缀的调色板索引；
 * 函数用 dst[2]=style 切换选中/未选中颜色。
 *
 * 汉化后文本变成 F9 80 hi lo 短语引用，dst[2] 恰是短语码高字节，
 * 再写 style 会指错短语（护符/地图名等）。F9 短语没有颜色前缀，
 * 因此当 dst[0]==0xF9 时跳过 dst[2]=style。
 */
#include "game.h"

#define ADDR_MENU_PRINT_TEXT  0x0806F16Cu

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

void DrawOptionMenuChoice_hook_C(const uint8_t *text,
                                  uint32_t x, uint32_t y, uint32_t style)
{
    uint8_t dst[16];
    unsigned i = 0;

    while (text[i] != 0xFF && i < 15u) {
        dst[i] = text[i];
        i++;
    }

    /* 原版: dst[2] = style。F9 短语没有 FC 颜色前缀，跳过。 */
    if (dst[0] != 0xF9u)
        dst[2] = (uint8_t)style;

    dst[i] = 0xFF;

    ((menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u))(dst, x, y);
}
