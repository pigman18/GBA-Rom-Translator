@ =============================================================================
@ game.bin: JP PokeNav tip print @ 0x080EA6C8 (kind, index)
@ 覆盖整个函数：Blank tip 矩形后 Menu_PrintText。
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global PokeNav_PrintMenuTip_Hook
    .thumb_func
    .type PokeNav_PrintMenuTip_Hook, %function
    .extern PokeNav_PrintMenuTip_hook_C

PokeNav_PrintMenuTip_Hook:
    push {lr}
    bl PokeNav_PrintMenuTip_hook_C
    pop {r1}
    bx r1
    .size PokeNav_PrintMenuTip_Hook, .-PokeNav_PrintMenuTip_Hook
