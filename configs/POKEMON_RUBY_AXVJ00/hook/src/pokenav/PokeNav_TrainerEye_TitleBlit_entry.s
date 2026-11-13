@ game.bin: 80925BC-compatible title blit (r0=str, r1=dest, r2/r3=colors)
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_TitleBlit_Hook
    .thumb_func
    .type PokeNav_TrainerEye_TitleBlit_Hook, %function
    .extern PokeNav_TrainerEye_TitleBlit_hook_C

PokeNav_TrainerEye_TitleBlit_Hook:
    push {lr}
    bl PokeNav_TrainerEye_TitleBlit_hook_C
    pop {r1}
    bx r1
    .pool

    .size PokeNav_TrainerEye_TitleBlit_Hook, .-PokeNav_TrainerEye_TitleBlit_Hook
