/* ============================================================================
 * InitTextPrinter_hook.c — v22：**块边界钩**（唯一职责 = 行相位按块复位）
 *
 * ## 为什么需要这个钩子
 * `InitTextPrinter 0x08002C68` 是「一条文本串（= 一个文本块）」的起点。
 * 行相位 `v8_phase` 的行键 = `f(win, tpl, CUR_Y, CUR_TILE_Y)`（见 tile_alloc.c）
 * —— **不含 CUR_X**。设置页实测同一行上有多个块
 * （`(15,5) / (19,5) / (23,5)`，`.tmp/smp2.txt`）⇒ 它们**共用行键** ⇒ 后一块
 * 带着前一块的相位起步：12px 步进下相位为 4 ⇒ 首字左移半列；同时
 * `TILE_OFFSET` 被 `InitTextPrinter` 清零（`0x08002CA4 strh r6,[r0,#24]`）
 * 而相位没清 ⇒ **号与列错配**。这是设置页错位的第二个成因。
 * 故在**每次块边界**显式复位相位；块内的换行（FE）仍由行键自动检出。
 *
 * ## 为什么不再改 TILE_BASE
 * v21 的「窗口私有画布」（chs_canvas）**从未生效**：门控
 * `tpl->tileData == 0x06000000` 对文本层恒不成立（文本层 charBase 2
 * ⇒ `0x06008000`），且它依赖的「cb 区空闲带」已被
 * `.cursor/rules/axvj-no-avoidance-band.mdc` 判为违规。本钩子因此**原样返回**
 * `tile_base`，号完全由 `PrintNextChar_hook.c::chs_claim_tile` 的纯函数算出：
 *
 *     tile = TILE_BASE + block_base(CUR_X, CUR_Y) + TILE_OFFSET
 *
 * 详见 `include/game.h` 的 `CHS_TILE_SPACE` 段（v22 方案 H）。
 *
 * ## 原序言重放（跳板约定，见 src/text/entry.s）
 *   C68 push{r4,r5,r6,lr}    ← ROM 桩已做
 *   C6A..C6E mov r6,sb / mov r5,r8 / push{r5,r6}
 *   C70 ldr r4,[sp,#0x18] / C72 mov sb,r4   ← 跳板重放
 * ==========================================================================*/
#include "text.h"
#include "tile_alloc.h"

/* 参数：win / tile_base(r2) / cur_x(r3) / cur_y(第 5 参数，栈)。
 * 返回：本窗口最终要用的 tile_base —— v22 恒为原值（不再改画布）。 */
uint16_t InitTextPrinter_hook_C(TextPrinter *win, uint16_t tile_base,
                                uint8_t cur_x, uint8_t cur_y)
{
    (void)cur_x;
    (void)cur_y;

    if (!win)
        return tile_base;

    /* 块边界 ⇒ 新的一条串从 CUR_X 起画，相位必须从 0 开始。 */
    v8_phase_reset();

    return tile_base;
}
