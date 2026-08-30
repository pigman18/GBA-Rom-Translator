/* =====================================================================================
 * fontfunc_hook.c — v5 FontFuncTable 重定向 thunk（混合写入架构步骤 2）
 *
 * hook 面：本文件 + hooks_origin.s 是 v5 文本引擎的**唯一 ROM hook**——
 * FontFuncTable@0x081BB3AC 的 4 个表项（tm0..tm3）改指本文件的 4 个 thunk。
 * 官方 PrintNextChar 对可印字符（含 0xF9——官方只拦 0xFA-0xFF）分发
 * FontFuncTable[textMode](win, c)，因此：
 *
 *   thunk(win, c) = TranslateHandleChar(win, c)（F9 协议 / SLT2 slot 替换，
 *                   src/text_translater.c，已消费则返回）
 *                 ‖ 尾调原生处理器（未消费的 JP PCS 字节，行为与原版逐字节一致）
 *
 * 防递归铁律：原生分发必须**直调 Origin 地址常量**，严禁经 FontFuncTable——
 * 表项已指向我方 thunk，经表分发 = 无限递归（DrawGlyph 同理共用 NativeDispatch）。
 *
 * v4 的 P01（PrintNextChar 整函数替换）/ P05（等 A 箭头跳板）/ P24
 * （InitWindowTileData 分区器）随本架构废止：官方状态机自行处理
 * FA-FF 控制码与 FC 子码（sub_8003110 原生存在），16px 整格无相位状态
 * 可同步，中文 tile 不再踩预渲染字库（落点只在 TILE_BASE+TILE_OFFSET 游标）。
 * ===================================================================================== */
#include "text.h"

typedef void (*fontfunc_t)(TextPrinter *, uint32_t);

/* 原生处理器分发：直调 Origin 地址（thumb 位显式置 1）。
 * textMode 4-7 无表项（FontFuncTable 仅 4 项，JP 引擎不会产生），静默消费。 */
void FontFunc_NativeDispatch(uint8_t tm, TextPrinter *win, uint32_t c)
{
    fontfunc_t fn;

    switch (tm & 7u) {
    case 0:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM0_ORIGIN | 1u);
        break;
    case 1:
        fn = (fontfunc_t)(ADDR_PRINT_GLYPH_TM1_ORIGIN | 1u);
        break;
    case 2:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM2_ORIGIN | 1u);
        break;
    case 3:
        fn = (fontfunc_t)(ADDR_FONT_FUNC_TM3_ORIGIN | 1u);
        break;
    default:
        return;
    }
    fn(win, c);
}

/* ---- 4 个表项 thunk（game_syms.asm 发射，hooks_origin.s 引用）---- */

void FontFuncTm0_Hook(TextPrinter *win, uint32_t c)
{
    if (TranslateHandleChar(win, c))
        return;
    FontFunc_NativeDispatch(0, win, c);
}

void FontFuncTm1_Hook(TextPrinter *win, uint32_t c)
{
    if (TranslateHandleChar(win, c))
        return;
    FontFunc_NativeDispatch(1, win, c);
}

void FontFuncTm2_Hook(TextPrinter *win, uint32_t c)
{
    if (TranslateHandleChar(win, c))
        return;
    FontFunc_NativeDispatch(2, win, c);
}

void FontFuncTm3_Hook(TextPrinter *win, uint32_t c)
{
    if (TranslateHandleChar(win, c))
        return;
    FontFunc_NativeDispatch(3, win, c);
}
