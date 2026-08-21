/* GetStringWidth.c — CHS 文本流像素宽度计算（纯工具，无 hook 挂点）。
 *
 * 语义（2026-08-22 反汇编 + GDB 实测钉死，见 MapNamePopup_hook.c 头注）：
 *   - 0x00 空白与 JP 字面量 = 8px（CHS_GLYPH_ADVANCE_JP_PX，
 *     DrawGlyph_CHS → PrintGlyph_Tiles_CHS_Adv(8u)）；
 *   - F9 00 内联汉字 = 12px（CHS_GLYPH_ADVANCE_PX）；
 *   - F9 80 短语引用 = 查 ADDR_PHRASE_OFFSETS/ADDR_PHRASE_TABLE 走短语流
 *     逐字累加（查表失败退化为一个汉字宽）；
 *   - FA~FE 控制码 = 0px（渲染不推进）；
 *   - 0xFF 终止。
 *
 * 注意：步进值是「本引擎实际渲染步进」，与 textMode=3 弹窗等半格场景一致；
 * 若未来有按 16px 全格步进的场景，应另算，不要改这里（记账：2026-08-22）。
 */
#include "game.h"

#define GETSTR_CTRL_BASE 0xFAu   /* ≥ 此值的单字节为控制码（0px，不推进） */
#define GETSTR_PHRASE_WALK_MAX 256u

/* F9 80 短语流宽度：流内汉字 12px、字面量 8px、控制码 0px。 */
static uint32_t phrase_width_px(const uint8_t *stream)
{
    uint32_t w = 0;
    uint32_t i = 0;

    if (!stream)
        return CHS_GLYPH_ADVANCE_PX;    /* 查表失败退化为一个汉字宽 */
    while (i < GETSTR_PHRASE_WALK_MAX && stream[i] != 0xFF) {
        uint8_t c = stream[i];
        if (c == CHS_ESCAPE) {
            if (stream[i + 1] == 0)
                w += CHS_GLYPH_ADVANCE_PX;
            i += 4;
            continue;
        }
        if (c >= GETSTR_CTRL_BASE) {
            i += 1;
            continue;
        }
        w += CHS_GLYPH_ADVANCE_JP_PX;
        i += 1;
    }
    return w;
}

/* F9 单元宽度：p[0]=F9，p[1]=op；00=内联汉字(12px)，80=短语引用(逐字累加)。 */
static uint32_t unit_width_px(const uint8_t *p)
{
    const uint32_t *offsets = (const uint32_t *)ADDR_PHRASE_OFFSETS;
    uint16_t code = (uint16_t)((p[2] << 8) | p[3]);
    uint32_t off;

    if (p[1] == 0)
        return CHS_GLYPH_ADVANCE_PX;
    if (code >= 0x2000u)
        return CHS_GLYPH_ADVANCE_PX;
    off = offsets[code];
    if (off >= 0x01000000u)
        return CHS_GLYPH_ADVANCE_PX;
    return phrase_width_px((const uint8_t *)ADDR_PHRASE_TABLE + off);
}

uint32_t GetStringWidth_PCS(const uint8_t *buf, uint32_t max_bytes)
{
    uint32_t w = 0;
    uint32_t len = 0;

    while (len < max_bytes && buf[len] != 0xFF) {
        if (buf[len] == CHS_ESCAPE && len + 3 < max_bytes) {
            w += unit_width_px(&buf[len]);
            len += 4;
        } else if (buf[len] >= GETSTR_CTRL_BASE) {
            len += 1;                   /* 控制码 0px */
        } else {
            w += CHS_GLYPH_ADVANCE_JP_PX; /* 0x00 与 JP 字面量同 8px */
            len += 1;
        }
    }
    return w;
}
