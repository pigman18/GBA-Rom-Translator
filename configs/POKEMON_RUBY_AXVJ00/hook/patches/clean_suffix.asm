; =============================================================================
; [P13~P16] pokedex unit "Zhi" + badge unit "Ge"
; pokeRS-style: .loadtable + .strn
; AXVJ encodes Han as F9 00 ll tt (see patches/chs_unit_charmap.txt)
;
; Dex (append after ConvertIntToFullwidth; was hiragana hiki):
;   0x08090EF0, 0x08090F3C  -> r0 cursor
;   0x08090FAA              -> r4 cursor
; Badge (static string; was hiragana ko @ 0x081BC164, ptr @ 0x080077A0)
; =============================================================================

.loadtable "./patches/chs_unit_charmap.txt"

.org 0x081DA780
.align 2
SuffixZhi:
    .strn "只$"
SuffixGe:
    .strn "个$"

.align 2
AppendPcsAtR0:
    push    {r1-r3}
    mov     r2, #0
AppendPcs_loop:
    ldrb    r3, [r1, r2]
    strb    r3, [r0, r2]
    add     r2, #1
    cmp     r3, #0xFF
    bne     AppendPcs_loop
    pop     {r1-r3}
    bx      lr

.align 2
AppendZhi_R0:
    push    {r1, lr}
    ldr     r1, =SuffixZhi
    bl      AppendPcsAtR0
    pop     {r1, pc}
    .pool

.align 2
AppendZhi_R4:
    push    {r0, r1, lr}
    mov     r0, r4
    ldr     r1, =SuffixZhi
    bl      AppendPcsAtR0
    pop     {r0, r1, pc}
    .pool

; --- dex: three sites append Zhi ---
.org 0x08090EF0
    bl      AppendZhi_R0
    nop
    nop
    nop
    nop

.org 0x08090F3C
    bl      AppendZhi_R0
    nop
    nop
    nop
    nop

.org 0x08090FAA
    bl      AppendZhi_R4
    nop
    nop
    nop
    nop

; --- badge: point to Ge; clear old ko ---
.org 0x080077A0
    .word   SuffixGe

.org 0x081BC164
    .byte   0xFF
    .byte   0xFF
