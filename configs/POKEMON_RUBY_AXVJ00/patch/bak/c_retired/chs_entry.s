@ =============================================================================
@ game.bin 入口薄壳：保持 ProcessCurrentChar 原寄存器约定
@ 入：r3=当前字符，r4=TextPrinter；栈上已有 saved r4、返回地址
@ 出：C 返回 1 → pop r4/lr；返回 0 → 原版 FontFuncTable
@ Thumb-1（arm7tdmi）：用 adds/movs/lsls
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified
    .global ChineseGlyphDispatch
    .thumb_func
    .type ChineseGlyphDispatch, %function
    .global FarBxR3
    .thumb_func
    .type FarBxR3, %function
    .extern ChineseGlyphDispatch_C

ChineseGlyphDispatch:
    adds r0, r4, #0              @ win
    adds r1, r3, #0              @ cur_char
    push {r3, r4}                @ 供回退原版路径恢复
    bl ChineseGlyphDispatch_C
    pop {r3, r4}
    cmp r0, #0
    beq Cgd_original
    movs r0, #1
    pop {r4}
    pop {r1}
    bx r1

@ 非 F9：查 FontFuncTable[font] 再 CallViaR2
Cgd_original:
    ldr r0, =0x081BB3AC          @ FontFuncTable
    ldrb r1, [r4, #0x0A]         @ WIN_FONTNUM
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
    .size ChineseGlyphDispatch, .-ChineseGlyphDispatch
