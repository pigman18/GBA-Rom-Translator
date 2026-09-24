/* ============================================================================
 * chs_canvas.h — v21「窗口私有画布」分配器
 *
 * 背景（15-0b 逐指令实证）
 * ========================
 * 日版引擎本来就是「位置定号 + 每窗口一块私有基址」：
 *   · `InitTextPrinter(win, text, tile_base, x, y)` → `win[0x16] = tile_base`（u16）
 *   · `UpdateTilemap` 把 `tile | (win[0x0F] << 12)` **原样**写进 tilemap 项，
 *     **不加 charBase 偏移** ⇒ tile 号是 **0..1023 的全局号**，
 *     物理地址 = `tpl->tileData + tile*32`（号空间 = 该窗口 charBase 起 32 KB）。
 *   · `InitWindowTileData` 的字形 worker 只对 **textMode == 1** 加载 ⇒
 *     tm0 窗口的画布是纯净的（官方一个字节都不放）。
 *
 * 🔴🔴 2026-09-20 实测结论：**「静态池」这条路线不成立**（数据已裁决）
 * ============================================================================
 * 🚫 本文件的做法（固定号区间 + 块轮转）命中 `.cursor/rules/axvj-no-avoidance-band.mdc`
 *    的**字符串级禁令**：`POOL_LO` 属于「`*_LO` 且赋值为 0x1..0x3FF 的起点常量」，
 *    配套的 `scripts/verify_pool_safety.py` 属于「扫/采样 VRAM 找空档再塞 tile」。
 *    该规则要求此种修法**先停问用户**，不得自行调区间。
 *
 * 数据（`scripts/verify_pool_safety.py`，输入 `.tmp/ss{1..6}_*.bin`）
 * ----------------------------------------------------------------------------
 * 判据必须是「**BG 的 tilemap 有没有引用这个号**」，且号必须**按 charBase 归位**：
 *     全局号 gnum = charBase*512 + tile_index   （charBase = BGxCNT bits2-3）
 * 🔴 旧分析把 `tile_index` 当全局号 ⇒ 「处处冲突」的假象；两次结论都因此作废。
 *
 * 归位后的事实：
 *   · 文本层 = **BG0**（screenBase 30/31），charBase 常为 **2** ⇒ 号 **[1024,2048)**；
 *     美术层 = BG1/BG2/BG3，charBase 常为 **0** ⇒ 号 [0,1024)。
 *   · 号 [0,1024) 被美术层引用 **312 个** ⇒ **v21 的池 `[0,384)` 正压在美术
 *     tileset 上**（这是「崩得更厉害」的结构性原因之一）。
 *   · 换到文本层自己的号段也一样：号 [1024,2048) 的**六场景并集空闲段**
 *     只有 `[1824,2024)` 200 号 / `[1683,1809)` 126 号 / 其余 ≤17 号；
 *     曾经的候选 `[252,512)` 在归位后有 **149 号冲突** ⇒ 同样作废。
 *   ⇒ **不存在足以放画布的稳定连续段**，静态避让带已在数据上判死。
 *
 * 另一条实测（gdb 断点 + EWRAM 状态表，2026-09-20）
 * ----------------------------------------------------------------------------
 * 自测链路已通（Qt mGBA stub + `arm-none-eabi-gdb`；断点机制经 IRQ handler 验证有效），
 * 但**手上的 savestate 全是 7~8 月旧构建**（romCrc 不匹配被测 ROM），装载后画面
 * 不再重画 ⇒ 25s 内 `chs_canvas_base_for` / `InitTextPrinter_hook_C` /
 * `PrintNextChar_Hook` 断点 **0 命中**，态表 `0x0203FF50` **magic=0**。
 * ⚠ 这**不能**证明门控恒假 —— 没有文字要画时本来就不会命中。
 * ⇒ 要判「门控是否成立 / 同屏几个中文窗口」，必须有一个**能触发文字重画**的
 *   当前构建 savestate（或可自动化的按键输入；当前 mGBA 构建无 `--script`，
 *   `SendKeys` 被 `mgba-script-input-only.mdc` 禁止）。
 *
 * 为什么只对 `charBase == 0` 的窗口启用（历史理由，保留备查）
 * =====================================
 * 号是「相对该窗口 charBase」的。BG 的 charBase 组合随场景变化，无法静态锁定。
 * ==========================================================================*/
#ifndef CHS_CANVAS_H
#define CHS_CANVAS_H

#include <stdint.h>
#include "game.h"

/* ⚠ 下面这组常量**没有安全取值**，见文件头（2026-09-20 数据裁决）。
 * 保持与已出 ROM 一致的原值，勿再「换个区间」了事。 */
#define CHS_CANVAS_POOL_LO   0u
#define CHS_CANVAS_POOL_SIZE 384u
#define CHS_CANVAS_BLOCKS    2u
#define CHS_CANVAS_BLOCK_SZ  (CHS_CANVAS_POOL_SIZE / CHS_CANVAS_BLOCKS)  /* 192 */

/* 取（或首次分配）窗口实例的画布基址。
 * 同一 win 实例恒定返回同一基址；新实例按块轮转领一块。
 * 块只决定**起点** —— 窗口的 TILE_OFFSET 是纯线性推进、**不设上界**，
 * 所以「同屏只有 1 个中文窗口」时它会自然用满整池（384 号）。 */
uint16_t chs_canvas_base_for(TextPrinter *win);

/* 冷启动清零（EWRAM 内容不保证为零）。幂等。 */
void chs_canvas_init_once(void);

#endif /* CHS_CANVAS_H */
