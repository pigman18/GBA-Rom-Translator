@ game.bin: JP Trainer Eye left panel @ 0x080EBA40 (mode)
@ 整函数接管：chs_bg0 锁内重印标签/数字。
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_LeftPanel_Hook
    .thumb_func
    .type PokeNav_TrainerEye_LeftPanel_Hook, %function
    .extern PokeNav_TrainerEye_LeftPanel_hook_C

PokeNav_TrainerEye_LeftPanel_Hook:
    push {lr}
    bl PokeNav_TrainerEye_LeftPanel_hook_C
    pop {r1}
    bx r1
    .pool

    .size PokeNav_TrainerEye_LeftPanel_Hook, .-PokeNav_TrainerEye_LeftPanel_Hook
