@ game.bin: JP SummaryScreen_PrintMetLevel @ 0x0809CFA0
@ (mon, a, b, left, top) — top 在 [sp]；bx 跳板保留 lr，C 直接返回调用方
    .syntax unified
    .thumb
    .text

    .global SummaryScreen_PrintMetLevel_Hook
    .thumb_func
    .type SummaryScreen_PrintMetLevel_Hook, %function
    .extern SummaryScreen_PrintMetLevel_hook_C

SummaryScreen_PrintMetLevel_Hook:
    ldr r4, =SummaryScreen_PrintMetLevel_hook_C
    bx r4
    .pool

    .size SummaryScreen_PrintMetLevel_Hook, .-SummaryScreen_PrintMetLevel_Hook
