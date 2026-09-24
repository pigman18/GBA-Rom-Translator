; Hook at default case in GetStringWidth loop.
; Replaces 'adds r6, #1' (start of 'add width and call GetGlyphWidth').
.org GetStringWidth + 0x0C
    push lr
    ldr r3, =(GetStringWidthChinese | 1)
    bl Gswc_HookFar
    pop r0
    mov r14, r0
    b GetStringWidth + 0x1E
Gswc_HookFar:
    bx r3
.pool
