@ =============================================================================
@ game.bin 入口：对应 pokeruby PrintNextChar 常规字形支
@ AXVJ equ: ProcessCurrentChar / ProcessCurrentChar_RegularGlyph
@ 入：r3=当前字符，r4=Window/TextPrinter；栈上 saved r4、返回地址
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
    .extern PrintNextChar_C
    .extern GetStringWidthChinese_Full
    .extern MapName_DisplayCellLength_C

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

@ pokeruby GetStringWidth ABI: r0=win, r1=str → r0=width
GetStringWidthChinese:
    push {lr}
    bl GetStringWidthChinese_Full
    pop {r1}
    bx r1
    .size GetStringWidthChinese, .-GetStringWidthChinese

@ DrawMapNamePopup: replace BL StringLength. r0=str → r0=cell_len, then
@ resume at movs r1,#10 (overwritten by the 8-byte far bx hook + pool).
MapName_DisplayCellLength:
    push {lr}
    bl MapName_DisplayCellLength_C
    pop {r3}
    movs r1, #10
    ldr r3, =0x0809F689
    bx r3
    .pool
    .size MapName_DisplayCellLength, .-MapName_DisplayCellLength
