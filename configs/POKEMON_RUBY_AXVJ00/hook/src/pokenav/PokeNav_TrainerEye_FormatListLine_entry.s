@ game.bin: JP Trainer Eye list line format @ 0x080F228C (dest, index)
@ 整函数接管：按像素垫职业列后再拼名字。
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_FormatListLine_Hook
    .thumb_func
    .type PokeNav_TrainerEye_FormatListLine_Hook, %function
    .extern PokeNav_TrainerEye_FormatListLine_hook_C

PokeNav_TrainerEye_FormatListLine_Hook:
    push {lr}
    bl PokeNav_TrainerEye_FormatListLine_hook_C
    pop {r1}
    bx r1
    .pool

    .size PokeNav_TrainerEye_FormatListLine_Hook, .-PokeNav_TrainerEye_FormatListLine_Hook
