/* MapNamePopup_hook.c — 地名弹窗居中钩（P04，挂 DrawMapNamePopup StringLength 位点 0x0809F67E）。
 *
 * 背景：AXVJ 原生按「字节格」在 10 格字段居中（全部 16px/格），译后地名是内联
 * F9 流，字节≠宽度，>10B 时 10-len 下溢野写（历史 crash 根因）。
 *
 * 方案 v4（2026-08-22 GDB 单步实证两连修）：
 *   1) ROM 补丁严禁占用 r0 —— native `mov r0,sp` 的缓冲区指针必须原样进 C
 *      （v1~v3 补丁用 ldr r0 转跳，C 收到的是跳板自身地址 0x08800145，
 *      把机器码当名字量宽 → 恒 152px，三代全中同一枪）。
 *   2) MenuPrint 的 x/left 参数是**格数**（8px/格），Text_InitWindow 内
 *      win->left = 8*left（pokeruby text.c 实证 + v4 实测像素直传出界 wrap
 *      确认）。返回值改为居中起点格数（四舍五入，残差 ≤4px）。
 * 关键事实（反汇编实证）：
 *   - 本引擎实际步进：0x00 空白与 JP 字面量 = 8px（DrawGlyph_CHS 的
 *     PrintGlyph_Tiles_CHS_Adv(8u) 与 CHS_GLYPH_ADVANCE_JP_PX）；F9 汉字 =
 *     12px（PrintGlyph_CHS 的 CHS_GLYPH_ADVANCE_PX）。
 *   - 缓冲区仅 20B（sub sp,#0x14），塞空白方案对长名字节预算不够；
 *     调 left 后无缓冲区约束，sid=78 五字名（恰 20B）也能居中。
 *
 * 入口 r0=sp 缓冲区（只读遍历），返回居中追加**格数**（0 = 维持原生位置）。
 * 跳板落点 0x0809F6CE（跳过 movs r1,#1），由跳板注入 r1 = 1 + 返回值。
 * 安全阀：宽度为 0 或 > 160px（10 格）→ 返回 0 原样放行；left 为 u8，
 * 1+留白 ≤ 11 格不会截断。
 *
 * 已知边界（记账）：FA~FE 控制码按 0px 跳过（地名表中不出现）；sectionId==0x42
 * 走原生旁路不经过本钩（维持原生行为）；半宽字面量已按真实 8px 计入，无偏差。
 */
#include "game.h"

#define MAPNAME_FIELD_PX    80u /* 文字区 10 列 × 8px（textMode=3 半格步进，v5 实测反推） */
#define MAPNAME_BUF_BYTES  20   /* 原生 sub sp,#0x14 */
#define MAPNAME_CELL_PX      8u /* x 参数粒度 = 空白/JP 字面量步进 */
#define MAPNAME_CTRL_BASE 0xFAu

/* F9 80 短语流宽度：流内汉字 12px、字面量 8px、控制码 0px。 */
static uint32_t phrase_width_px(const uint8_t *stream)
{
    uint32_t w = 0;
    uint32_t i = 0;

    if (!stream)
        return CHS_GLYPH_ADVANCE_PX;    /* 查表失败退化为一个汉字宽 */
    while (i < 256u && stream[i] != 0xFF) {
        uint8_t c = stream[i];
        if (c == CHS_ESCAPE) {
            if (stream[i + 1] == 0)
                w += CHS_GLYPH_ADVANCE_PX;
            i += 4;
            continue;
        }
        if (c >= MAPNAME_CTRL_BASE) {
            i += 1;
            continue;
        }
        w += MAPNAME_CELL_PX;
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

uint32_t MapNamePopup_CalcLeftPx(const uint8_t *buf)
{
    uint32_t width_px = 0;
    int len = 0;

    while (len < MAPNAME_BUF_BYTES && buf[len] != 0xFF) {
        if (buf[len] == CHS_ESCAPE && len + 3 < MAPNAME_BUF_BYTES) {
            width_px += unit_width_px(&buf[len]);
            len += 4;
        } else if (buf[len] >= MAPNAME_CTRL_BASE) {
            len += 1;                   /* 控制码 0px（表中不存在） */
        } else {
            width_px += MAPNAME_CELL_PX;/* 0x00 与 JP 字面量同 8px */
            len += 1;
        }
    }

    if (width_px == 0 || width_px >= MAPNAME_FIELD_PX)
        return 0;                       /* 空/满宽：原样放行 */
    /* 居中起点换算成「格」（8px）：MenuPrint 的 left 是格数，Text_InitWindow
     * 内 win->left = 8*left（pokeruby text.c 实证；2026-08-22 v4 实测像素
     * 直传按格×8 出界 wrap）。
     * 文字区总宽 = 10 列 × 8px = 80px（v5 实测反推：left=9 格时第三字出框、
     * left=7 格时后两字出框，框右缘均 ≈88px；textMode=3 每字符步进 8px，
     * 与原生「10 字符字段 + left=1」自洽）。
     * 四舍五入取格，残差 ≤4px。跳板注入 r1 = 1 + 返回值（基准 = 第 1 格）。 */
    return (((MAPNAME_FIELD_PX - width_px) / 2u) + (MAPNAME_CELL_PX / 2u)) / MAPNAME_CELL_PX;
}
