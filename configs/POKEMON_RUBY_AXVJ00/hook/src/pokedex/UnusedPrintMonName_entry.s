@ =============================================================================
@ game.bin: JP UnusedPrintMonName @ 0x0808DD60 (name, left, top)
@ 覆盖整个函数：右对齐分类名进问号区后 Menu_PrintText（后缀留给占位串）。
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global UnusedPrintMonName_Hook
    .thumb_func
    .type UnusedPrintMonName_Hook, %function
    .extern UnusedPrintMonName_hook_C

UnusedPrintMonName_Hook:
    push {lr}
    bl UnusedPrintMonName_hook_C
    pop {r1}
    bx r1
    .size UnusedPrintMonName_Hook, .-UnusedPrintMonName_Hook