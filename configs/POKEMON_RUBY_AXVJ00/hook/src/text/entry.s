@ =============================================================================
@ text/entry.s — v6：仅 PrintNextChar 入口；UpdateTilemap 不劫 ROM
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
    .extern PrintNextChar_Hook

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

.end
