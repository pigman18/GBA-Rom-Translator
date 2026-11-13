@ =============================================================================
@ game.bin: JP UnusedPrintDecimalNum @ 0x0808DDD4 (value, left, top)
@ 覆盖整个函数：清占位后右对齐打印数字+单位。
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global UnusedPrintDecimalNum_Hook
    .thumb_func
    .type UnusedPrintDecimalNum_Hook, %function
    .extern UnusedPrintDecimalNum_hook_C

UnusedPrintDecimalNum_Hook:
    push {lr}
    bl UnusedPrintDecimalNum_hook_C
    pop {r1}
    bx r1
    .size UnusedPrintDecimalNum_Hook, .-UnusedPrintDecimalNum_Hook
