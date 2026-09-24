/* DrawOptionMenuChoice_hook — 设置窗口选项高亮绘制。
 *
 * 原版：FC 05 <palette> ，dst[2]=style 切换调色板。
 * 翻译后：F9 80 hi lo 短语引用，短语流内自带 FC 05 0F，会覆盖外层 style。
 *
 * ✅ 真正生效的修复 = **在 dst 前面补 `FC 05 <style>`**（下面的 dst[0..2]）：
 *    引擎的 FC 05 处理器写 `win[0x0F]`，`UpdateTilemap` 再按
 *    `tile | (win[0x0F] << 12)` 落 tilemap ⇒ **选中项拿到 bank 8 = 红**。
 *
 * 🔴 ADDR_OPT_PALETTE_OVERRIDE 是**死代码**：全仓库只写不读（2026-09-21 全目录
 *    grep 确认）。留着只是历史包袱，别指望它 —— 调色板靠上面那个 FC 05。
 *
 * 🔴 ADDR_OPT_FG_COLOR 会**真的**改 ink 色（PrintNextChar_hook.c 读它）。
 *   2026-09-21 把 OPT_FG_SELECTED 从 8 改成 1：原盘红字 ink 索引 = 1，
 *     bank 8 的 index 1 = 红、bank 9 的 index 1 = 黑 ⇒ 红黑全由 bank 承担，
 *     引擎一个字形像素都不改。填 8 会撞上**阴影色索引 8**（win[0x0E]=8）
 *     ⇒ ink 与阴影同色 ⇒ 笔画被自身阴影撑粗融合 = 中文「一坨红」。
 *     详见 include/game.h 的 OPT_FG_SELECTED 注释。
 */
#include "game.h"

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
