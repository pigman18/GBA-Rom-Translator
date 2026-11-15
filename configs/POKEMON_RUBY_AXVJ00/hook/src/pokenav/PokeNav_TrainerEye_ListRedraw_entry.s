@ game.bin: blank list window then resume JP ListRedraw @ 0x080EBD2C
@ hooks_origin stub = ldr+bx+.pool = 8B → resume 0x080EBD34.
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_ListRedraw_Hook
    .thumb_func
    .type PokeNav_TrainerEye_ListRedraw_Hook, %function
    .extern PokeNav_TrainerEye_ListBlank_C

PokeNav_TrainerEye_ListRedraw_Hook:
    push {r4, r5, lr}
    adds r4, r0, #0
    adds r5, r1, #0
    /* r0=index r1=y — 按行 Blank */
    bl PokeNav_TrainerEye_ListBlank_C
    adds r0, r4, #0
    adds r1, r5, #0
    pop {r4, r5}
    pop {r3}
    mov lr, r3
    /* stolen prologue from 0x080EBD2C..EBD33 (8B) */
    push {r4, r5, r6, r7, lr}
    sub sp, #20
    lsls r0, r0, #16
    lsrs r6, r0, #16
    ldr r3, =(0x080EBD34 | 1)
    bx r3
    .pool

    .size PokeNav_TrainerEye_ListRedraw_Hook, .-PokeNav_TrainerEye_ListRedraw_Hook
