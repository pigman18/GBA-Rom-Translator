@ game.bin: JP PrintTrainerMemo 遭遇行公共 Menu_PrintText @ 0x0809D1DE
@ 订址桩已把 r0=template / r1=left / r2=top 摆好；印完跳回 epilogue。
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global SummaryScreen_PrintMetDesc_Hook
    .thumb_func
    .type SummaryScreen_PrintMetDesc_Hook, %function
    .extern SummaryScreen_PrintMetDesc_hook_C

SummaryScreen_PrintMetDesc_Hook:
    push {lr}
    bl SummaryScreen_PrintMetDesc_hook_C
    pop {r1}
    ldr r3, =(0x0809D216 | 1)
    bx r3
    .pool

    .size SummaryScreen_PrintMetDesc_Hook, .-SummaryScreen_PrintMetDesc_Hook
