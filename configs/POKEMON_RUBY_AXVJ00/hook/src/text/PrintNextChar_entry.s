@ =============================================================================
@ game.bin entry: pokeruby PrintNextChar / AXVJ PrintNextChar RegularGlyph
@ In: r3=cur char, r4=TextPrinter; stack has saved r4 + return
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified
    .global PrintNextChar
    .thumb_func
    .type PrintNextChar, %function
    .global FarBxR3
    .thumb_func
    .global GetStringWidthChinese
    .thumb_func
    .type GetStringWidthChinese, %function
    .global MapName_DisplayCellLength
    .thumb_func
    .type MapName_DisplayCellLength, %function
    .global WaitArrow_Prepare
    .thumb_func
    .type WaitArrow_Prepare, %function
    .extern PrintNextChar_C
    .extern GetStringWidthChinese_Full
    .extern WaitArrow_Prepare_C

PrintNextChar:
    adds r0, r4, #0
    adds r1, r3, #0
    push {r3, r4}
    bl PrintNextChar_C
    pop {r3, r4}
    cmp r0, #0
    beq Pnc_original
    movs r0, #1
    pop {r4}
    pop {r1}
    bx r1

Pnc_original:
    ldr r0, =0x081BB3AC          @ FontFuncTable
    ldrb r1, [r4, #0x0A]
    lsls r1, r1, #2
    adds r1, r1, r0
    ldr r2, [r1]
    adds r0, r4, #0
    adds r1, r3, #0
    ldr r3, =0x081B12DD          @ CallViaR2 | 1
    bl FarBxR3
    movs r0, #1
    pop {r4}
    pop {r1}
    bx r1

FarBxR3:
    bx r3
    .pool
    .size PrintNextChar, .-PrintNextChar

@ pokeruby GetStringWidth ABI: r0=win, r1=str → r0=width (no ROM hook this pass)
GetStringWidthChinese:
    push {lr}
    bl GetStringWidthChinese_Full
    pop {r1}
    bx r1
    .size GetStringWidthChinese, .-GetStringWidthChinese

@ DrawMapNamePopup @0x0809F67E: skip StringLength pad + 2nd GetMapName(fill).
@ First GetMapName(fill=0) already left raw F9…FF on sp; MenuPrint reloads r0=sp.
@ 原版在 StringLength 后仍 GetMapName(fill=10) 填 0x00，把中文 F9 短语顶出
@ 白空格（Bug1）并二次覆盖导致重复（Bug2）。直跳 MenuPrint 跳过 pad/二次 fill。
MapName_DisplayCellLength:
    ldr r3, =0x0809F6CB
    bx r3
    .pool
    .size MapName_DisplayCellLength, .-MapName_DisplayCellLength

@ DrawInitialDownArrow @0x08003F4C — sync CHS cursor then vanilla body.
WaitArrow_Prepare:
    push {r0, lr}
    bl WaitArrow_Prepare_C
    pop {r0, r3}
    movs r1, #0
    strh r1, [r0, #6]
    push {r3}
    ldr r3, =0x08003DAD
    bl FarBxR3
    pop {r1}
    bx r1
    .pool
    .size WaitArrow_Prepare, .-WaitArrow_Prepare
