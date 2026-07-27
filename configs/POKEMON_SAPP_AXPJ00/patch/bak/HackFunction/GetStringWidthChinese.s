; F9-aware string width measurement.
; Called from GetStringWidth default case hook (0x08004CCC).
;
; Encoding:
;   F9 00 <lead> <trail>  — one glyph
;   F9 XX <high> <low>    — phrase (XX≠0); XX=7F auto / 01–7E sticky (width ignores XX)
;
; Entry: r5=win, r7=s, r6=i, r2=width, r1=s[i]
; Exit:  r6=updated i, r2=updated width, bx lr

GetStringWidthChinese:
    cmp r1, #0xF9
    bne Gswc_default

    push {r3-r4, lr}
    add r0, r7, r6               ; r0 = &s[i]
    ldrb r3, [r0, #1]            ; r3 = s[i+1] (channel / op)

    cmp r3, #0
    beq Gswc_f900
    ; F9 XX≠0 — phrase (7F default / 01–7E write.op)
    b Gswc_phrase

Gswc_f900:
    ; F9 00 — width must match Draw (2 tile cols = 16px Normal).
    ldrb r1, [r5, #WIN_FONTNUM]
    cmp r1, #FONT_NORMAL_UNSHADOWED
    beq Gswc_w16
    cmp r1, #FONT_NORMAL_SHADOWED
    beq Gswc_w16
    mov r0, #10
    b Gswc_add
Gswc_w16:
    mov r0, #16
Gswc_add:
    add r2, r0
    lsl r2, r2, #24
    lsr r2, r2, #24
    add r6, #4
    b Gswc_return

Gswc_phrase:
    ldrb r4, [r0, #2]
    ldrb r0, [r0, #3]
    lsl r4, r4, #8
    orr r4, r0
    ldr r0, =PhraseOffsets
    lsl r1, r4, #1
    ldrh r1, [r0, r1]
    ldr r0, =PhraseTable
    add r0, r1
    ldrb r3, [r0]
    ldrb r1, [r5, #WIN_FONTNUM]
    cmp r1, #FONT_NORMAL_UNSHADOWED
    beq Gswc_p16
    cmp r1, #FONT_NORMAL_SHADOWED
    beq Gswc_p16
    lsl r0, r3, #3
    lsl r1, r3, #1
    add r0, r1
    b Gswc_padd
Gswc_p16:
    lsl r0, r3, #4
Gswc_padd:
    add r2, r0
    lsl r2, r2, #24
    lsr r2, r2, #24
    add r6, #4

Gswc_return:
    pop {r3-r4, lr}
    bx lr

Gswc_default:
    add r6, #1
    mov r0, r5
    str r2, [sp]
    push {lr}
    ldr r3, =(GetGlyphWidth | 1)
    bl Gswc_FarBxR3
    pop {r3}
    mov r14, r3
    ldr r2, [sp]
    add r0, r2, r0
    lsl r0, r0, #24
    lsr r2, r0, #24
    bx lr

Gswc_FarBxR3:
    bx r3
.pool
