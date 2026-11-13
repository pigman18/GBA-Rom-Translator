@ game.bin: JP Trainer Eye red-bar title @ 0x080EF558 (r0=str)
@ F7 两列写入 dest 后 DMA；替代无 F7 的 80925BC。
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_PrintTitle_Hook
    .thumb_func
    .type PokeNav_TrainerEye_PrintTitle_Hook, %function
    .extern PokeNav_TrainerEye_PrintTitle_hook_C

PokeNav_TrainerEye_PrintTitle_Hook:
    push {lr}
    bl PokeNav_TrainerEye_PrintTitle_hook_C
    pop {r1}
    bx r1
    .pool

    .size PokeNav_TrainerEye_PrintTitle_Hook, .-PokeNav_TrainerEye_PrintTitle_Hook
