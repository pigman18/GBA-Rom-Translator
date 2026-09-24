@ =============================================================================
@ text/entry.s — 文本层入口跳板（2026-09-22 · v1 8px 渲染层）
@
@ EngineEntry 必须 link 第一（= game.bin 首地址 = main.asm 的 JP2CHS_Entry）。
@ hooks_origin.s 把 PrintNextChar@0x080032F8 的头 8B 换成 ldr/bx 到本处。
@
@ 「未消费则交回原版」由 C 侧完成（C 直接调 PrintNextChar_Origin）：
@   EngineEntry 是**尾跳** ⇒ C 函数的 return 直接回到 PrintNextChar 的调用方，
@   所以这里没有分支逻辑，只是入口。
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
    .extern PrintNextChar_Hook

EngineEntry:
    ldr r1, =PrintNextChar_Hook
    bx  r1
    .pool

@ 原版 PrintNextChar 头 8B 被钩子盖掉，这里逐条重放后从 0x08003300 续跑：
@   080032F8  push {r4, lr}        ← 本处重放
@   080032FA  adds r4, r0, #0      ← 本处重放
@   080032FC  ldrh r0, [r4, #0x14] ← 本处重放
@   080032FE  adds r1, r0, #1      ← 本处重放
@   08003300  strh r1, [r4, #0x14] ← 从这里续跑（0x08003301 = 带 thumb 位）
PrintNextChar_Origin:
    push    {r4, lr}
    adds    r4, r0, #0
    ldrh    r0, [r4, #0x14]
    adds    r1, r0, #1
    ldr     r2, =0x08003301
    bx      r2
    .pool
    .size PrintNextChar_Origin, .-PrintNextChar_Origin

@ 完整原生 UpdateTilemap @0x080036DC（未劫 ROM）：中文打印层专用。
@ 语义（逐指令核过）：写 up 到当前格、low 到下一 map 行(+32 格)，palette 位取自 win[+0x0F]，
@ 不推进任何游标 ⇒ 调用方自己推 win[0x1B]。
UpdateTilemap_Origin:
    ldr     r3, =0x080036DD
    bx      r3
    .pool
    .size UpdateTilemap_Origin, .-UpdateTilemap_Origin

.end
