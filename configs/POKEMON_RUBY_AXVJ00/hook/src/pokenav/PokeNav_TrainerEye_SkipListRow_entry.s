@ game.bin: skip list-row redraw during detail enter @ 0x080EC364
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_SkipListRow_Hook
    .thumb_func
    .type PokeNav_TrainerEye_SkipListRow_Hook, %function
    .extern PokeNav_TrainerEye_SkipListRow_hook_C

PokeNav_TrainerEye_SkipListRow_Hook:
    push {lr}
    bl PokeNav_TrainerEye_SkipListRow_hook_C
    pop {r1}
    bx r1
    .pool

    .size PokeNav_TrainerEye_SkipListRow_Hook, .-PokeNav_TrainerEye_SkipListRow_Hook
