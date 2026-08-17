/* UnusedPrintMonName_hook — 图鉴分类名行：直接 name + 「宝可梦」，
 * 不再右对齐到占位符「？？？？？宝可梦」。
 *
 * JP UnusedPrintMonName @ 0x0808DD60（美版 0x08091304）：
 *   r0=name(0x00结尾), r1=left(CATEGORY_LEFT=13), r2=top(=5)
 * 美版逻辑：把 name 拷贝后 MenuPrint_AlignedToRightOfReferenceString 右对齐
 * 到 gDexText_UnknownPoke 宽度 → 中文 12px/字 与 问号 8px/字 覆盖不齐
 * （2字盖不满剩问号 / 4字溢出吞「宝」）。
 * 本 hook：直接拼接 name + 「宝可梦」短语，左对齐打印即可。
 */
#include "game.h"

#define ADDR_MENU_PRINT_TEXT     0x0806F16Cu  /* Menu_PrintText(str,left,top) */

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

void UnusedPrintMonName_hook_C(const uint8_t *name,
                               uint32_t left, uint32_t top)
{
    uint8_t str[32];
    unsigned i = 0;

    while (name[i] != 0x00 && i < 11u) {
        str[i] = name[i];
        i++;
    }
    str[i] = 0xFF;

    ((menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u))(str, left, top);
}
