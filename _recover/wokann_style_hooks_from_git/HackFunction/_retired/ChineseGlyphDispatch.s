; AXVJ Chinese dispatcher — F9 draw path
; Encoding:
;   F9 00 <lead> <trail>   — side font; sticky=0 (auto/geometry)
;   F9 7F <high> <low>     — phrase; sticky=0 (auto) — default phrase channel
;   F9 01..7E <hi> <lo>    — phrase; sticky = XX (write.op; 02=footer 03=linear 04=slot)
;   bare FA..FF            — PCS controls / EOS (NOT F9 channels)
;
; EnsureLinearTileBump (charBase==0): raise WIN_TILE_OFFSET so JP nick
; cannot rewind over battle-menu Chinese VRAM.
; Skip when TILE_BASE >= 0x280 (move/type/PP fixed slots).

ChineseGlyphDispatch:
    ldr r0, [r4, #WIN_TEMPLATE]
    ldrb r0, [r0, #1]
    cmp r0, #0
    bne Cgd_after_bump
    ldrh r0, [r4, #WIN_TILE_BASE]
    ldr r1, =0x280
    cmp r0, r1
    bhs Cgd_after_bump
    push {r1-r2}
    ldr r0, =ChineseTileState
    ldrh r1, [r0]
    cmp r1, #0
    bne Cgd_bump_pop
    ldrh r1, [r0, #4]
    cmp r1, #4
    blo Cgd_bump_pop
    ldrh r2, [r4, #WIN_TILE_BASE]
    cmp r1, r2
    bls Cgd_bump_pop
    sub r1, r1, r2
    ldr r2, =0x180
    cmp r1, r2
    blo Cgd_bump_apply
    mov r1, #0x60
    ldrh r2, [r4, #WIN_TILE_BASE]
    add r2, r1
    strh r2, [r0, #4]
Cgd_bump_apply:
    ldrh r2, [r4, #WIN_TILE_OFFSET]
    cmp r2, r1
    bhs Cgd_bump_pop
    strh r1, [r4, #WIN_TILE_OFFSET]
Cgd_bump_pop:
    pop {r1-r2}
Cgd_after_bump:
    cmp r3, #0xF9
    bne Cgd_original

    push {r5-r7}
    ldr r1, [r4, #WIN_TEXT_PTR]
    ldrh r2, [r4, #WIN_TEXT_INDEX]
    add r0, r1, r2
    ldrb r7, [r0]

    cmp r7, #0
    beq Cgd_chinese_char
    ; F9 7F → phrase auto; F9 01..7E → phrase + sticky=XX
    b Cgd_phrase_op

; ── F9 00 — single Chinese char (auto) ───────────────────────────────────
Cgd_chinese_char:
    cmp r2, #1
    bne Cgd_f900_body
    ldr r5, =ChineseTileState
    mov r6, #0
    strb r6, [r5, #2]
Cgd_f900_body:
    add r0, #1
    ldrb r6, [r0]
    add r0, #1
    ldrb r5, [r0]

    cmp r6, #0xFA
    bcs Cgd_not_chinese
    cmp r5, #0xFA
    bcs Cgd_not_chinese
    cmp r6, #0x01
    blt Cgd_not_chinese
    cmp r6, #0x1E
    bgt Cgd_not_chinese
    cmp r6, #0x06
    beq Cgd_not_chinese
    cmp r6, #0x1B
    beq Cgd_not_chinese

    add r2, #3
    strh r2, [r4, #WIN_TEXT_INDEX]

    mov r1, r6
    cmp r1, #6
    blt Cgd_sub1
    cmp r1, #0x1B
    blt Cgd_sub2
    sub r1, #1
Cgd_sub2:
    sub r1, #1
Cgd_sub1:
    sub r1, #1
    lsl r1, r1, #8
    add r1, r5

    ldr r0, =7168
    cmp r1, r0
    bcs Cgd_done_ok

    ldr r0, =FontChsNormal
    lsl r1, r1, #7
    add r6, r0, r1
    bl DrawChineseGlyph4bpp
    b Cgd_done_ok

; ── F9 XX <high> <low> — phrase ──────────────────────────────────────────
; XX==7F → sticky 0 (auto geometry)
; XX=01..7E → sticky = XX (02=footer clears linear HW; 03/04=linear/slot)
Cgd_phrase_op:
    ldr r5, =ChineseTileState
    cmp r7, #0x7F
    beq Cgd_phrase_auto
    strb r7, [r5, #2]
    cmp r7, #3
    bhs Cgd_phrase_load
    mov r6, #0
    strh r6, [r5, #4]              ; clear linear HW for footer (op=2)
    b Cgd_phrase_load
Cgd_phrase_auto:
    mov r6, #0
    strb r6, [r5, #2]                  ; sticky=auto only — do NOT clear +4 HW
                                       ; (menu rows share Linear bump; clear → 三行同字)
Cgd_phrase_load:
    add r0, #1
    ldrb r5, [r0]
    add r0, #1
    ldrb r6, [r0]
    add r2, #3
    strh r2, [r4, #WIN_TEXT_INDEX]

    lsl r5, r5, #8
    orr r5, r6

    ldr r0, =PhraseOffsets
    lsl r1, r5, #1
    ldrh r1, [r0, r1]
    ldr r0, =PhraseTable
    add r0, r1
    ldrb r7, [r0]

    mov r0, #0

Cgd_phrase_loop:
    cmp r0, r7
    bhs Cgd_phrase_done
    push {r0}

    ldr r0, =PhraseOffsets
    lsl r1, r5, #1
    ldrh r1, [r0, r1]
    ldr r0, =PhraseTable
    add r1, r0
    add r1, #2

    ldr r2, [sp]
    lsl r2, r2, #1
    ldrh r1, [r1, r2]

    ldr r0, =FontChsNormal
    lsl r1, r1, #7
    add r6, r0, r1

    bl DrawChineseGlyph4bpp

    pop {r0}
    add r0, #1
    b Cgd_phrase_loop

Cgd_phrase_done:
    ; Do NOT blank with TILE_BASE+0 — that tile is window chrome, causes
    ; left-edge / cursor garbage. Short CN clear is Mode2 grid + erase window.
    b Cgd_done_ok

Cgd_done_ok:
    mov r0, #1
    pop {r5-r7}
    pop {r4}
    pop {r1}
    bx r1

Cgd_not_chinese:
    pop {r5-r7}

Cgd_original:
    ldr r0, =FontFuncTable
    ldrb r1, [r4, #WIN_FONTNUM]
    lsl r1, r1, #2
    add r1, r0
    ldr r2, [r1]
    mov r0, r4
    mov r1, r3
    ldr r3, =(CallViaR2 | 1)
    bl Cgd_FarBxR3
    mov r0, #1
    pop {r4}
    pop {r1}
    bx r1

Cgd_FarBxR3:
    bx r3

FarBxR3:
    bx r3
.pool
