@ game.bin: JP PokemonSummaryScreen_PrintTrainerMemo @ 0x0809D03C
@ r0=mon, r1=left, r2=top；整函数接管后直接返回。
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global SummaryScreen_PrintTrainerMemo_Hook
    .thumb_func
    .type SummaryScreen_PrintTrainerMemo_Hook, %function
    .extern SummaryScreen_PrintTrainerMemo_hook_C

SummaryScreen_PrintTrainerMemo_Hook:
    push {lr}
    bl SummaryScreen_PrintTrainerMemo_hook_C
    pop {r1}
    bx r1
    .pool

    .size SummaryScreen_PrintTrainerMemo_Hook, .-SummaryScreen_PrintTrainerMemo_Hook
