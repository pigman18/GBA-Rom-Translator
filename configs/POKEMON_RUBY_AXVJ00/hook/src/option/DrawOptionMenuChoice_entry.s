@ =============================================================================
@ game.bin: JP DrawOptionMenuChoice @ 0x080889F0 (text, x, y, style)
@ main.asm 已 push {r3} 保留 style；此处恢复后再调 C。
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global DrawOptionMenuChoice_Hook
    .thumb_func
    .type DrawOptionMenuChoice_Hook, %function
    .extern DrawOptionMenuChoice_hook_C

DrawOptionMenuChoice_Hook:
    pop {r3}
    push {lr}
    bl DrawOptionMenuChoice_hook_C
    pop {r1}
    bx r1
    .size DrawOptionMenuChoice_Hook, .-DrawOptionMenuChoice_Hook
