@ game.bin: JP Trainer Eye detail enter @ 0x080EBF9C
@ 打印说明指针前清右栏列表残墨 + 左栏统计字。
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_DetailEnter_Hook
    .thumb_func
    .type PokeNav_TrainerEye_DetailEnter_Hook, %function
    .extern PokeNav_TrainerEye_DetailEnter_hook_C

PokeNav_TrainerEye_DetailEnter_Hook:
    push {lr}
    bl PokeNav_TrainerEye_DetailEnter_hook_C
    pop {r1}
    bx r1
    .pool

    .size PokeNav_TrainerEye_DetailEnter_Hook, .-PokeNav_TrainerEye_DetailEnter_Hook
