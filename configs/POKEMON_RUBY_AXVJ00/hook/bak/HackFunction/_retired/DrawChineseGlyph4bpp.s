; Draw one 16x16 4bpp Chinese glyph into the current JP TextPrinter window.
; In: r4 = win, r6 = src (0x80 bytes, 2x2 tiles column-major: TL,BL,TR,BR)
;
; write.op sticky (ChineseTileState+2, set by F9 XX phrase channel):
;   unset/0 / F9 7F → geometry gate (default phrase)
;   0x02    → 2D; footer band only if y>=16 (party prompt top=17)
;   0x03    → Draw_Linear (battle)
;   0x04    → Draw_Linear (BASE>=0x280 uses local offset only)
;   write.op 01..7E; bare FA..FF = PCS (not F9 channels)
;
; Config: write.op only for 02/03/04; shop/summary rely on geometry.
; Hard overrides (above sticky):
;   TILE_BASE >= 0x280 → local_slot linear
;   charBase == 0      → battle linear
;
; auto geometry (legacy):
;   charBase2+font3 + left<20 → Linear (shop/field dialogue; Mode2 ghosts into box line2)
;   left>=20 → Mode2 + MENU_BAND 0x100 (party action / summary)
; FOOTER sticky (op 0x02) → Mode2 + FOOTER_BAND when y>=16.

CHS_TILE_GRID_W         equ 30
CHS_TILE_POOL_END       equ 0x180
CHS_LINEAR_STICKY_END   equ 0x60
CHS_MENU_LINEAR_FLOOR   equ 0x100
CHS_MODE2_FOOTER_BAND   equ 0x100
CHS_MODE2_MENU_BAND     equ 0x100
; Skip window-frame tiles near TILE_BASE (+2 was too small → grey border).
CHS_MODE2_ORIGIN        equ 0x20
CHS_PARTY_MENU_LEFT     equ 20
CHS_PARTY_MENU_TOP      equ 12
CHS_BATTLE_FIXED_BASE   equ 0x280
CHS_WRITE_AUTO          equ 0
CHS_WRITE_GRID          equ 1
CHS_WRITE_FOOTER        equ 2
CHS_WRITE_LINEAR        equ 3
CHS_WRITE_SLOT          equ 4
WIN_FONTNUM_REAL        equ 0x0B

DrawChineseGlyph4bpp:
    push {r4-r7, lr}
    mov r7, r4
    mov r5, r6

    ; Clear sticky write.type when charBase changes (avoid battle→party bleed)
    ldr r0, [r7, #WIN_TEMPLATE]
    ldrb r1, [r0, #1]                  ; charBase
    ldr r0, =ChineseTileState
    ldrh r2, [r0]
    cmp r1, r2
    beq Draw_cb_same
    strh r1, [r0]
    mov r2, #0
    strb r2, [r0, #2]
Draw_cb_same:

    ; Hard: battle fixed slots
    ldrh r1, [r7, #WIN_TILE_BASE]
    ldr r2, =CHS_BATTLE_FIXED_BASE
    cmp r1, r2
    bhs Draw_Linear

    ; Hard: charBase 0 → linear
    ldr r0, [r7, #WIN_TEMPLATE]
    ldrb r1, [r0, #1]
    cmp r1, #0
    beq Draw_Linear

    ; Sticky write.type
    ldr r0, =ChineseTileState
    ldrb r1, [r0, #2]
    cmp r1, #CHS_WRITE_GRID
    beq Draw_Mode2
    cmp r1, #CHS_WRITE_FOOTER
    beq Draw_Mode2
    cmp r1, #CHS_WRITE_LINEAR
    beq Draw_Linear
    cmp r1, #CHS_WRITE_SLOT
    beq Draw_Linear
    ; auto / unknown → geometry

    ldr r0, [r7, #WIN_TEMPLATE]
    ldrb r1, [r0, #1]                  ; charBaseBlock
    cmp r1, #2
    bne Draw_Linear
    ldrb r1, [r7, #WIN_FONTNUM_REAL]
    cmp r1, #3
    bne Draw_Linear
    ldrb r1, [r7, #0x1A]               ; print left
    cmp r1, #CHS_PARTY_MENU_LEFT
    bhs Draw_Mode2                     ; party action / summary: Mode2 + MENU_BAND
    b Draw_Linear                      ; shop / field dialogue: Linear (no Mode2 ghost)

Draw_Linear:
    bl AllocLinearTile
    strh r1, [r7, #WIN_TILE_OFFSET]

    bl DrawLinearColumn0
    ldrh r0, [r7, #WIN_TILE_OFFSET]
    add r0, #2
    strh r0, [r7, #WIN_TILE_OFFSET]
    ldrb r0, [r7, #WIN_CURSOR_TILE_X]
    add r0, #1
    strb r0, [r7, #WIN_CURSOR_TILE_X]

    bl DrawLinearColumn1
    ldrh r0, [r7, #WIN_TILE_OFFSET]
    add r0, #2
    strh r0, [r7, #WIN_TILE_OFFSET]
    ldrb r0, [r7, #WIN_CURSOR_TILE_X]
    add r0, #1
    strb r0, [r7, #WIN_CURSOR_TILE_X]

    ; abs high-water — skip for battle fixed slots (BASE>=0x280)
    ldrh r1, [r7, #WIN_TILE_BASE]
    ldr r2, =CHS_BATTLE_FIXED_BASE
    cmp r1, r2
    bhs Draw_Done
    ldr r0, =ChineseTileState
    ldrh r2, [r7, #WIN_TILE_OFFSET]
    ldr r3, =CHS_TILE_POOL_END
    cmp r2, r3
    blo Draw_hw_ok
    ldrh r3, [r0]
    cmp r3, #0
    bne Draw_hw_ok
    ldr r2, =CHS_LINEAR_STICKY_END
    strh r2, [r7, #WIN_TILE_OFFSET]
Draw_hw_ok:
    add r1, r1, r2
    ldrh r2, [r0, #4]
    cmp r1, r2
    bls Draw_Done
    strh r1, [r0, #4]
    b Draw_Done

Draw_Mode2:
    bl ComputeCursorTilePair
    mov r6, r1
    mov r4, r2

    ldr r3, [r7, #WIN_TEMPLATE]
    ldr r0, [r3, #0x0C]
    lsl r1, r6, #5
    add r1, r0, r1
    mov r0, r5
    bl CopyTileViaVanilla
    ldr r3, [r7, #WIN_TEMPLATE]
    ldr r0, [r3, #0x0C]
    lsl r1, r4, #5
    add r1, r0, r1
    mov r0, r5
    add r0, #0x20
    bl CopyTileViaVanilla
    mov r0, r7
    mov r1, r6
    mov r2, r4
    ldr r3, =(UpdateTilemap | 1)
    bl FarBxR3

    ldrb r0, [r7, #WIN_CURSOR_TILE_X]
    add r0, #1
    strb r0, [r7, #WIN_CURSOR_TILE_X]

    bl ComputeCursorTilePair
    mov r6, r1
    mov r4, r2

    ldr r3, [r7, #WIN_TEMPLATE]
    ldr r0, [r3, #0x0C]
    lsl r1, r6, #5
    add r1, r0, r1
    mov r0, r5
    add r0, #0x40
    bl CopyTileViaVanilla
    ldr r3, [r7, #WIN_TEMPLATE]
    ldr r0, [r3, #0x0C]
    lsl r1, r4, #5
    add r1, r0, r1
    mov r0, r5
    add r0, #0x60
    bl CopyTileViaVanilla
    mov r0, r7
    mov r1, r6
    mov r2, r4
    ldr r3, =(UpdateTilemap | 1)
    bl FarBxR3

    ldrb r0, [r7, #WIN_CURSOR_TILE_X]
    add r0, #1
    strb r0, [r7, #WIN_CURSOR_TILE_X]

Draw_Done:
    pop {r4-r7}
    pop {r0}
    bx r0

; Out: r1=upper, r2=lower
; Band (away from frame @ TILE_BASE+0):
;   sticky==FOOTER(2) y>=16 → FOOTER_BAND + y'  (op 0x02 only)
;   sticky==0 left>=20 → MENU_BAND + ▶ inset
;   (auto left<20 uses Draw_Linear — never calls this)
ComputeCursorTilePair:
    push {r4-r5, lr}
    ldrb r0, [r7, #0x1A]
    ldrb r1, [r7, #WIN_CURSOR_TILE_X]
    add r0, r0, r1                     ; x
    ldrb r1, [r7, #WIN_CURSOR_Y]
    ldrb r2, [r7, #WIN_CURSOR_TILE_Y]
    add r1, r1, r2                     ; y

    mov r4, #0                         ; band bias
    ldr r5, =ChineseTileState
    ldrb r5, [r5, #2]
    cmp r5, #CHS_WRITE_FOOTER
    beq Compute_footer_y
    cmp r5, #0
    bne Compute_y_ok
    ldrb r5, [r7, #0x1A]
    cmp r5, #CHS_PARTY_MENU_LEFT
    bhs Compute_menu_band              ; party action / summary
    b Compute_y_ok                     ; auto shop/dialogue: no FOOTER_BAND
Compute_footer_y:
    cmp r1, #16
    blo Compute_y_ok
    sub r1, #16
    ldr r4, =CHS_MODE2_FOOTER_BAND
    add r0, #1
    b Compute_y_ok
Compute_menu_band:
    add r0, #1                         ; ▶ cursor column
    ldr r4, =CHS_MODE2_MENU_BAND       ; past shared frame (no Linear → 取消取消)
Compute_y_ok:
    lsl r2, r1, #4
    sub r2, r2, r1
    lsl r2, r2, #1                     ; y*30
    add r2, r2, r0
    add r2, r2, r4                     ; + footer band
    ldrh r3, [r7, #WIN_TILE_BASE]
    add r2, r2, r3
    add r2, #CHS_MODE2_ORIGIN          ; past frame chrome (not +2)
    lsl r2, r2, #16
    lsr r1, r2, #16                    ; upper
    mov r2, r1
    add r2, #CHS_TILE_GRID_W           ; lower = upper + 30
    pop {r4-r5}
    pop {r0}
    bx r0

; Out: r1 = local offset
; Abs bump keyed by charBase so dialogue Print cannot reset over menu glyphs.
; charBase 0 full → recycle at STICKY (never stick on END-4).
; TILE_BASE >= 0x280 → battle fixed slot: use win offset only (no global bump).
AllocLinearTile:
    push {lr}
    ldrh r1, [r7, #WIN_TILE_BASE]
    ldr r2, =CHS_BATTLE_FIXED_BASE
    cmp r1, r2
    blo Alloc_global
    ldrh r1, [r7, #WIN_TILE_OFFSET]    ; fixed slot: trust Text_InitWindow
    b Alloc_done
Alloc_global:
    ldr r0, [r7, #WIN_TEMPLATE]
    ldrb r1, [r0, #1]                  ; charBase
    ldr r0, =ChineseTileState
    ldrh r2, [r0]
    cmp r1, r2
    beq Alloc_same_cb
    strh r1, [r0]
    mov r3, #0
    strb r3, [r0, #2]                  ; clear write.type on charBase change
    ldrh r2, [r7, #WIN_TILE_BASE]
    cmp r1, #2
    beq Alloc_new_menu
    add r2, #4                         ; battle floor
    strh r2, [r0, #4]
    b Alloc_same_cb
Alloc_new_menu:
    ldr r1, =CHS_MENU_LINEAR_FLOOR
    add r2, r1
    strh r2, [r0, #4]                  ; next_abs = BASE+0x100
Alloc_same_cb:
    ldrh r1, [r7, #WIN_TILE_BASE]
    ldrh r2, [r7, #WIN_TILE_OFFSET]
    add r1, r1, r2                     ; abs_want
    ldrh r2, [r0, #4]                  ; next_abs
    cmp r1, r2
    bhs Alloc_have_abs
    mov r1, r2
Alloc_have_abs:
    ldrh r2, [r7, #WIN_TILE_BASE]
    sub r1, r1, r2                     ; local
    ldr r2, =CHS_TILE_POOL_END
    cmp r1, r2
    blo Alloc_floor_pick
    ldrh r2, [r0]
    cmp r2, #0
    bne Alloc_menu_or_clamp
    ldr r1, =CHS_LINEAR_STICKY_END
    ldrh r2, [r7, #WIN_TILE_BASE]
    add r2, r1
    strh r2, [r0, #4]
    b Alloc_floor_pick
Alloc_menu_or_clamp:
    cmp r2, #2
    bne Alloc_clamp_end
    ldr r1, =CHS_MENU_LINEAR_FLOOR     ; charBase2 recycle
    ldrh r2, [r7, #WIN_TILE_BASE]
    add r2, r1
    strh r2, [r0, #4]
    b Alloc_floor_pick
Alloc_clamp_end:
    ldr r1, =CHS_TILE_POOL_END
    sub r1, #4
Alloc_floor_pick:
    ldrh r2, [r0]                      ; charBase
    cmp r2, #2
    bne Alloc_min4
    ldr r2, =CHS_MENU_LINEAR_FLOOR
    cmp r1, r2
    bhs Alloc_done
    mov r1, r2
    b Alloc_done
Alloc_min4:
    cmp r1, #4
    bhs Alloc_done
    mov r1, #4
Alloc_done:
    pop {r0}
    bx r0

DrawLinearColumn0:
    push {lr}
    ldr r3, [r7, #WIN_TEMPLATE]
    ldrh r2, [r7, #WIN_TILE_BASE]
    ldrh r1, [r7, #WIN_TILE_OFFSET]
    add r2, r2, r1
    mov r6, r2
    mov r4, r2
    add r4, #1
    ldr r0, [r3, #0x0C]
    lsl r1, r6, #5
    add r1, r0, r1
    mov r0, r5
    bl CopyTileViaVanilla
    ldr r3, [r7, #WIN_TEMPLATE]
    ldr r0, [r3, #0x0C]
    lsl r1, r4, #5
    add r1, r0, r1
    mov r0, r5
    add r0, #0x20
    bl CopyTileViaVanilla
    mov r0, r7
    mov r1, r6
    mov r2, r4
    ldr r3, =(UpdateTilemap | 1)
    bl FarBxR3
    pop {r0}
    bx r0

DrawLinearColumn1:
    push {lr}
    ldr r3, [r7, #WIN_TEMPLATE]
    ldrh r2, [r7, #WIN_TILE_BASE]
    ldrh r1, [r7, #WIN_TILE_OFFSET]
    add r2, r2, r1
    mov r6, r2
    mov r4, r2
    add r4, #1
    ldr r0, [r3, #0x0C]
    lsl r1, r6, #5
    add r1, r0, r1
    mov r0, r5
    add r0, #0x40
    bl CopyTileViaVanilla
    ldr r3, [r7, #WIN_TEMPLATE]
    ldr r0, [r3, #0x0C]
    lsl r1, r4, #5
    add r1, r0, r1
    mov r0, r5
    add r0, #0x60
    bl CopyTileViaVanilla
    mov r0, r7
    mov r1, r6
    mov r2, r4
    ldr r3, =(UpdateTilemap | 1)
    bl FarBxR3
    pop {r0}
    bx r0

CopyTileViaVanilla:
    push {r2-r7, lr}
    ldrb r2, [r7, #WIN_COLOR_C]
    ldrb r3, [r7, #WIN_COLOR_E]
    ldrb r4, [r7, #WIN_COLOR_D]
    push {r4}
    ldr r4, =(CopyGlyph2bppTo4bpp | 1)
    bl FarBxR4
    add sp, #4
    pop {r2-r7}
    pop {r0}
    bx r0

FarBxR4:
    bx r4
.pool
