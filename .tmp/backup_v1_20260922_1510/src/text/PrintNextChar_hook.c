/* =====================================================================================
 * PrintNextChar_hook.c — 文本打印入口（2026-09-22 · v1 8px 渲染层）
 *
 * 职责只有一件事：把「翻译层/渲染层能消费的字符」吃掉，其余原样交回引擎。
 *
 *   ① 控制码 0xFA..0xFF        → 原版状态机（PrintNextChar_Origin）
 *   ② 可印字节：先自行推进 TEXT_INDEX 1 字节（与原版同序），再交 TranslateHandleChar：
 *        · F9 转义        → 翻译层解释（op=0 单汉字 / op!=0 短语）
 *        · 普通字节       → SLT2 slot 查表（命中即画中文）
 *      两路都返回 1 = 已消费。
 *   ③ 未消费（未翻译的日文/半角）→ 把 TEXT_INDEX 退回，交回原版原生绘制。
 *
 * 「交回原版」就是调用 PrintNextChar_Origin（entry.s 里重放被盖掉的序言后跳回
 * 0x08003300 续跑）——所以日文原文永远还有兜底，不会消失。
 *
 * ⚠ 顺序契约（与 text_translater.c 一致）：TranslateHandleChar 假定 TEXT_INDEX
 *   已指向当前字符之后（它用 pos = index-1 定位当前字符），故必须先推进 1 字节。
 * ===================================================================================== */
#include "text.h"

int PrintNextChar_Hook(TextPrinter *win)
{
    const uint8_t *text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    uint16_t idx = win_u16(win, WIN_TEXT_INDEX);
    uint8_t c = text[idx];

    if (c >= PCS_CTRL_BASE)          /* FA..FF：延迟/换行/清屏等，交原版 */
        return PrintNextChar_Origin(win);

    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx + 1u));
    if (TranslateHandleChar(win, c))
        return 1;

    win_set_u16(win, WIN_TEXT_INDEX, idx);   /* 未消费：退回，原版重读 */
    return PrintNextChar_Origin(win);
}
