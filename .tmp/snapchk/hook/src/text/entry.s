@ =============================================================================
@ text/entry.s — PrintNextChar 入口 + InitTextPrinter 块边界钩
@ UpdateTilemap_Origin = 直调完整原生 @0x080036DC（供中文打印层使用）
@ =============================================================================
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global EngineEntry
    .thumb_func
    .type EngineEntry, %function
    .global PrintNextChar_Origin
    .thumb_func
    .type PrintNextChar_Origin, %function
    .global UpdateTilemap_Origin
    .thumb_func
    .type UpdateTilemap_Origin, %function
    .global InitTextPrinter_Hook
    .thumb_func
    .type InitTextPrinter_Hook, %function
    .global SetWindowTileCache_Hook
    .thumb_func
    .type SetWindowTileCache_Hook, %function
    .extern PrintNextChar_Hook
    .extern InitTextPrinter_hook_C

EngineEntry:
    ldr r1, =PrintNextChar_Hook
    bx  r1
    .pool

@ P01 盖 8B（ldr+bx+pool @0x080032F8..FF）；从 0x08003300 起仍是原指令。
PrintNextChar_Origin:
    push    {r4, lr}
    adds    r4, r0, #0
    ldrh    r0, [r4, #0x14]
    adds    r1, r0, #1
    ldr     r2, =0x08003301
    bx      r2
    .pool
    .size PrintNextChar_Origin, .-PrintNextChar_Origin

@ 完整原生 UpdateTilemap（未劫 ROM）；中文打印层专用。
UpdateTilemap_Origin:
    ldr     r3, =0x080036DD
    bx      r3
    .pool
    .size UpdateTilemap_Origin, .-UpdateTilemap_Origin

@ [P0x] InitTextPrinter 块边界钩。
@ ROM 桩已 push{r4,r5,r6,lr}（真·调用者寄存器），再 ldr/bx 至此。
@ 此处补齐被 pool 盖掉的序言后半 + C 钩，再从 0x08002C74 续跑。
@ 原序言：
@   C68 push{r4,r5,r6,lr}   ← 桩已做
@   C6A mov r6,sb / C6C mov r5,r8 / C6E push{r5,r6}
@   C70 ldr r4,[sp,#0x18] / C72 mov sb,r4   ← 被 pool 覆盖，必须在此重放
@   C74 movs r4,#0 起完好 ← 跳回点
InitTextPrinter_Hook:
    mov     r6, sb
    mov     r5, r8
    push    {r5, r6}               @ 与原 C6E 对齐；此后 cur_y 在 [sp,#0x18]
    push    {r0, r1, r2, r3}       @ 保参（C 会砸 r1-r3）
    ldr     r4, [sp, #0x28]        @ cur_y：0x18 + 16
    adds    r1, r2, #0             @ r1 = tile_base
    adds    r2, r3, #0             @ r2 = cur_x
    adds    r3, r4, #0             @ r3 = cur_y
    bl      InitTextPrinter_hook_C
    @ 🔴 v22：**不再写回 r2 槽**。v21 在这里把 C 的返回值（私有画布基址）
    @ 覆盖 TILE_BASE；v22 的块基准位置定号必须用**引擎自己给的** TILE_BASE，
    @ 否则号会落到别的窗口的号段里。C 返回原值，此处只需观察，不写回。
    pop     {r0, r1, r2, r3}
    ldr     r4, [sp, #0x18]        @ 重放被盖掉的 ldr
    mov     sb, r4                 @ 重放 mov sb,r4
    ldr     r5, =0x08002C75        @ 续跑 movs r4,#0
    bx      r5
    .pool
    .size InitTextPrinter_Hook, .-InitTextPrinter_Hook

@ =============================================================================
@ [P34] 方案 B —— 把引擎字模整体推离文本层 charBlock。
@ -----------------------------------------------------------------------------
@ r0 = win, r1 = tileBase。
@
@ 实证（逐指令 + 42 份 IWRAM dump）：
@   · 引擎字模写 `tileData + (tileBase + index)*32`（font 0/3 走
@     `tileData + tileBase*32 + index*64`），index 遍历 [0,256)。
@   · 全部窗口 tpl[+8] == 3 ⇒ 走 512 号那条 ⇒ **字模占满整个 charBlock 还溢出 1 号**。
@   · 原生落砖函数的号 = `TILE_BASE + 2*glyph`（0x08003584 逐指令）——
@     TILE_BASE 直接加进 map 号，而预取写砖用的是 *0x0300032C（同一个值）。
@   ⇒ 所以「抬 tileBase」= 把字模与 map 号**同步平移**，引擎文字照常显示，
@     而我们的号池不用动（我方取号完全不依赖 TILE_BASE）。
@
@ 🔴🔴 「抬 tileBase 把字模搬去 cb3」这条方案 **已判死**（2026-09-21 实测）：
@   cb3（0x0600C000..0x06010000）不是空闲块 —— 它是 **screen block 24..31 的家**。
@   全部 14 个采样页的 BGxCNT 实测：sb ∈ {0,4,6,7,8,10,12,15,22,28,29,30,31}，
@   其中 28/29/30/31 的物理地址 0x0600E000/E800/F000/F800 **全在 cb3 内**。
@   抬 TB=512 ⇒ 字模写满 cb3 ⇒ 直接盖掉 tilemap（BG0 的 map 就在 sb=30 → 0x0600F000）
@   ⇒ 开机即崩。t12 的崩因就是它，不是「打桩漏了」。
@   而且 cb0/cb1/cb2 三个 charBlock 里**都不存在 16 KB 连续空闲段**（逐段核算过），
@   所以「给引擎字模另找一个块」这条路走不通。
@
@ ⇒ 本钩子退回**纯直通**（不改 tileBase），保留桩只为两件事：
@   1) 验证「新桩 + 跳板 + 续跑」这条管线本身正确（B 的机械部分将来还要用）；
@   2) 后续在这里加「引擎重写字模区」的代际计数器，用于让我们的砖缓存失效。
@
@ ⚠ 必须 `|1`：`bx` 到偶数地址会切 ARM 态执行 Thumb 代码 = 立刻崩。
@   本处曾漏（2026-09-21），t12/t13/t14 三次崩机的直接原因。
@ 栈净额：桩 push{lr}(-4)；本跳板 push{r4,r5}/pop{r4,r5}(0) ⇒ 与原函数一致。
@ 补完被桩覆盖的 5 条指令后从 0x0800295C（movs r0, #0）续跑。
SetWindowTileCache_Hook:
    push    {r4, r5}
    adds    r3, r0, #0              @ 补 2952：adds r3, r0, #0  (win)
    adds    r5, r1, #0              @ tileBase
    lsls    r5, r5, #16             @ 补 2954：lsls r1, r1, #16
    lsrs    r5, r5, #16             @ 补 2956：lsrs r1, r1, #16
    adds    r2, r5, #0              @ 补 2958：adds r2, r1, #0  (win[+0x16] 也写这个)
    ldr     r1, =0x0300032E         @ 补 295A：ldr r1, [pc, #48]
    pop     {r4, r5}
    ldr     r0, =0x0800295D         @ 续跑 0x0800295C（movs r0, #0）；|1 = 保持 Thumb
    bx      r0
    .pool
    .size SetWindowTileCache_Hook, .-SetWindowTileCache_Hook

.end
