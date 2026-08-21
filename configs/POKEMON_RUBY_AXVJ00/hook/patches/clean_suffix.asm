; =============================================================================
; [P13~P15] 图鉴计数「ひき」后缀置空（NOP）
; 三处函数在 ConvertIntToFullwidth 返回后硬编码写 1B 07 FF；
; 转换器本身已写 EOS(0xFF)，NOP 掉整组 6 条写入即可。
; 注意: 0x08090ECC/0x08090F18 用 R1，0x08090F70 用 R0
; =============================================================================

; --- [P13] 函数1 @0x08090ECC ---
.org 0x08090EF0
    nop                     ; MOV R1,#0x1B / STRB / MOV R1,#07 / STRB / MOV R1,#FF / STRB
    nop
    nop
    nop
    nop
    nop

; --- [P14] 函数2 @0x08090F18 = GetNationalPokedexCount ---
.org 0x08090F3C
    nop
    nop
    nop
    nop
    nop
    nop

; --- [P15] 函数3 @0x08090F70 = GetHoennPokedexCount（用 R0/R4）---
.org 0x08090FAA
    nop                     ; MOV R0,#0x1B / STRB R4 / MOV R0,#07 / STRB R4 / MOV R0,#FF / STRB R4
    nop
    nop
    nop
    nop
    nop

; --- [P16] 徽章屏文字后缀置空 ---
.org 0x081BC164
    .byte 0xFF
    .byte 0xFF
