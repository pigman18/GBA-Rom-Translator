/* UnusedPrintMonName_hook — 图鉴分类名行。
 *
 * 原日版逻辑：先把占位串「？？？？？ポケモン」打印到 (13,5)，再把分类名
 * 右对齐塞进 5 字节缓冲覆盖前 5 个问号（日文均为 8px/字）。
 *
 * 汉化后分类名变成 F9 80 hi lo FF 短语引用（12px/字），字节右对齐不再适用，
 * 会出现 2 字残问号 / 4 字吞「宝」。
 *
 * 本 hook：
 *   (1) 打印 10 个空格（每格 8px = 80px）把占位串
 *       「5问号40px + 宝可梦36px = 76px」整行擦掉；
 *   (2) 打印「分类名短语 + 宝可梦短语」，得到 XXX宝可梦。
 */
#include "game.h"

#define ADDR_MENU_PRINT_TEXT        0x0806F16Cu  /* Menu_PrintText(str,left,top) */
#define ADDR_DEX_TEXT_UNKNOWN_POKE  0x083E9688u  /* ？？？？？宝可梦 */

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);

#define NAME_MAX_BYTES  20u
#define CLEAR_SPACES    12u

void UnusedPrintMonName_hook_C(const uint8_t *name,
                               uint32_t left, uint32_t top)
{
    uint8_t str[64];
    uint8_t clear[CLEAR_SPACES + 1u];
    const uint8_t *ref = (const uint8_t *)ADDR_DEX_TEXT_UNKNOWN_POKE;
    unsigned i = 0;
    unsigned j;

    /* (1) 擦掉占位串整行（问号+宝可梦）。12 空格 = 96px ≥ 76px。 */
    for (j = 0; j < CLEAR_SPACES; j++)
        clear[j] = 0x00;
    clear[j] = 0xFF;
    ((menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u))(clear, left, top);

    /* (2) 拷贝分类名：F9 xx xx xx 短语整体 4 字节，遇 FF/00 停。 */
    while (i < NAME_MAX_BYTES && name[i] != 0xFF && name[i] != 0x00) {
        if (name[i] == 0xF9u && i + 3u < NAME_MAX_BYTES) {
            str[i] = name[i];
            str[i + 1u] = name[i + 1u];
            str[i + 2u] = name[i + 2u];
            str[i + 3u] = name[i + 3u];
            i += 4u;
        } else {
            str[i] = name[i];
            i++;
        }
    }

    /* (3) 接上占位串问号之后的「宝可梦」（f9 80 03 fa ff）。 */
    j = 0;
    while (ref[j] == 0xACu)   /* 跳过 ？？？ */
        j++;
    while (ref[j] != 0xFF && i + 1u < sizeof(str)) {
        str[i++] = ref[j++];
    }
    str[i] = 0xFF;

    ((menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u))(str, left, top);
}
