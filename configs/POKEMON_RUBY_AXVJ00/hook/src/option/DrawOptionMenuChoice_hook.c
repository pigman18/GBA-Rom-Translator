/* DrawOptionMenuChoice_hook — 设置窗口选项高亮绘制。
 *
 * 原版：FC 05 <palette> ，dst[2]=style 切换调色板。
 * 翻译后：F9 80 hi lo 短语引用，短语流内自带 FC 05 0F，会覆盖外层 style。
 *
 * 修复：打印前写入两个预留变量：
 *   ADDR_OPT_PALETTE_OVERRIDE = style                    强制 tilemap palette
 *   ADDR_OPT_FG_COLOR = 选中?大红:9 黑        强制 ink 前景色
 * 打印完清零。颜色可在 game.h OPT_FG_SELECTED/OPT_FG_UNSELECTED 调。
 */
#include "game.h"

#define ADDR_MENU_PRINT_TEXT   0x0806F16Cu
#define EXT_CTRL_CODE_BEGIN    0xFCu
#define EXT_CTRL_CODE_PALETTE  0x05u

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

void DrawOptionMenuChoice_hook_C(const uint8_t *text,
                                 uint32_t x, uint32_t y, uint32_t style)
{
    uint8_t dst[20];
    unsigned i = 0;
    unsigned off = 0;

    if (text[0] == 0xF9u) {
        dst[0] = EXT_CTRL_CODE_BEGIN;
        dst[1] = EXT_CTRL_CODE_PALETTE;
        dst[2] = (uint8_t)style;
        off = 3;
    }

    while (text[i] != 0xFF && i < 15u) {
        dst[off + i] = text[i];
        i++;
    }

    if (text[0] != 0xF9u)
        dst[2] = (uint8_t)style;

    dst[off + i] = 0xFF;

    *(volatile uint8_t *)ADDR_OPT_PALETTE_OVERRIDE = (uint8_t)style;
    *(volatile uint8_t *)ADDR_OPT_FG_COLOR =
        (style == 0x08u) ? (uint8_t)OPT_FG_SELECTED : (uint8_t)OPT_FG_UNSELECTED;
    ((menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u))(dst, x, y);
    *(volatile uint8_t *)ADDR_OPT_PALETTE_OVERRIDE = 0u;
    *(volatile uint8_t *)ADDR_OPT_FG_COLOR = 0u;
}
