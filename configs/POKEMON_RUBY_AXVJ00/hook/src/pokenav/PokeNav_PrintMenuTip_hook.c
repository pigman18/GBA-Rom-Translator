/* PokeNav_PrintMenuTip_hook — 领航员主菜单底部 tip。
 *
 * origin（AXVJ @ 0x080EA6C8）：
 *   str = TipTable[kind][index];
 *   Menu_PrintText(str, 4, 17);
 * 日版 tip 无 {CLEAR 0}、无 Align；靠 ROM 定长 0x00 空格整 tile 盖旧字。
 * 中文 0x00 只推进不重绘 + 译文去尾空格 → 短句盖不住上一句右端（残留「图」「带」）。
 *
 * 方案 A：仅在本场景钩内、打印前对 tip 行做 Menu_BlankWindowRect，
 * 不碰 PrintNextChar / 全局 clear_cols（避免开始菜单同 printer 误伤）。
 */
#include "game.h"

typedef void (*menu_print_t)(const uint8_t *str, uint32_t left, uint32_t top);
typedef void (*menu_blank_t)(uint32_t left, uint32_t top, uint32_t right,
                             uint32_t bottom);

/* tip 印在 (4,17)；字高 16px → tile 行 17..18。
 * 右界必须停在框内：origin tip 奶油底约到 px216（tile26），
 * tile27 起是边框/框外白底。Blank 用空白字模（奶油色）——
 * right=28 时会把黄条铺出边框（用户截图像「补空格」溢出）。 */
#define TIP_LEFT   3u
#define TIP_TOP    17u
#define TIP_RIGHT  26u
#define TIP_BOTTOM 18u
#define TIP_PRINT_X 4u
#define TIP_PRINT_Y 17u

void PokeNav_PrintMenuTip_hook_C(uint32_t kind, uint32_t index)
{
    const uint8_t *const *table;
    const uint8_t *str;
    menu_blank_t blank = (menu_blank_t)(ADDR_MENU_BLANK_WINDOW_RECT | 1u);
    menu_print_t print = (menu_print_t)(ADDR_MENU_PRINT_TEXT | 1u);

    kind &= 0xffu;
    index &= 0xffu;

    if (kind == 0u)
        table = (const uint8_t *const *)(uintptr_t)ADDR_POKENAV_TIP_TABLE0;
    else if (kind == 1u)
        table = (const uint8_t *const *)(uintptr_t)ADDR_POKENAV_TIP_TABLE1;
    else if (kind == 2u)
        table = (const uint8_t *const *)(uintptr_t)ADDR_POKENAV_TIP_TABLE2;
    else
        return;

    str = table[index];
    blank(TIP_LEFT, TIP_TOP, TIP_RIGHT, TIP_BOTTOM);
    print(str, TIP_PRINT_X, TIP_PRINT_Y);
}
