@ game.bin: 详情红条标题精灵路径 @ 0x080EF43C
@ 用 TitleBlit 替 80925BC，再回到 EF45C 原版建精灵。
    .cpu arm7tdmi
    .syntax unified
    .thumb
    .text
    .align 2

    .global PokeNav_TrainerEye_PrintTitleSprite_Hook
    .thumb_func
    .type PokeNav_TrainerEye_PrintTitleSprite_Hook, %function
    .extern PokeNav_TrainerEye_TitleBlit_hook_C

PokeNav_TrainerEye_PrintTitleSprite_Hook:
    push {r4, r5, r6, r7, lr}
    sub sp, #0xc
    adds r4, r0, #0                     @ str
    ldr r1, =0x083B4BAC
    ldr r3, [r1]
    ldr r2, =0xD1E4
    adds r1, r3, r2                     @ dest
    ldr r2, =0x001A0800
    str r1, [sp, #4]
    str r2, [sp, #8]
    ldr r7, =0x131E4
    adds r0, r3, r7
    str r0, [sp]
    adds r0, r4, #0
    movs r2, #1
    movs r3, #1
    bl PokeNav_TrainerEye_TitleBlit_hook_C
    add r0, sp, #4
    ldr r3, =(0x080EF45C | 1)
    bx r3
    .pool

    .size PokeNav_TrainerEye_PrintTitleSprite_Hook, .-PokeNav_TrainerEye_PrintTitleSprite_Hook
