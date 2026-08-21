/* GetGlyphWidth_hook.c — GetGlyphWidth 钩（C 实现，自 entry.s asm 移植）。
 *
 * ⚠ 未订 ROM 地址：实测 AXVJ 0x08004228 实为「窗口 spacing 表查表」
 * （walk {u32 key,u32 val}[] 终止于 key==0，匹配 win 字段，与 glyph 无关），
 * 本打印器步进由 PrintNextChar_C 自管（chs_px/last_adv），钩它无收益。
 * 若后续需要订址：main.asm `.org GetGlyphTilePointers` 同款重定位桩 +
 * entry.s 已备符号 GetGlyphWidthHook（pokeruby ABI r0=win,r1=glyph→r0）。
 *
 * 逻辑（与原 asm 逐条对应；×3 为历史 ABI 约定，保持不变）：
 *   glyph==F9 或 text[index]==F9 → fontNum 0/3 → 12，否则 10
 *   0x01..0x1E 且非 06/1B       → 4
 *   其余                        → 8
 */
#include "game.h"

uint32_t GetGlyphWidth_C(TextPrinter *win, uint32_t glyph)
{
    uint32_t width = 8;

    if (glyph == CHS_ESCAPE)
        goto chs;

    {
        const uint8_t *text =
            (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
        uint16_t index = win_u16(win, WIN_TEXT_INDEX);
        if (text[index] == CHS_ESCAPE)
            goto chs;
    }

    if (glyph >= 0x01u && glyph <= 0x1Eu && glyph != 0x06u && glyph != 0x1Bu)
        width = 4;
    goto done;

chs:
    {
        uint8_t font = win_u8(win, WIN_FONTNUM_REAL);
        width = (font == FONT_NORMAL_UNSHADOWED || font == FONT_NORMAL_SHADOWED)
                    ? 12u
                    : 10u;
    }

done:
    return width * 3u;
}
