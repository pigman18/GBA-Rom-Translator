; =============================================================================
; [P40] 存档确认信息框标签：扩大 sub sp + memcpy CopyLen
;
; 日版 PrintSave* 定长 memcpy 进 8B 栈（玩家/时间 CopyLen=7，图鉴=8），
; 重定位 F7 译文含 FF 共 9B → 截断无终止符 → 打印跑飞 + 右屏铺砖。
; 徽章本就 stack=16 / CopyLen=9，不动。
; 详见 docs/research/SAVE_MENU_CORRUPTION.md
;
; [P41] 徽章数后缀「こ」→「个」：
;   池 @0x08091404 改指 SuffixGe；原 memcpy CopyLen=2 只够 `0A FF`，
;   F7「个」需 5B → 扩栈 16→24、后缀落点 sp+12→+16、CopyLen 2→5。
; =============================================================================

; --- 玩家 PrintSavePlayerName：sub #8→#16，CopyLen 7→16，add #8→#16 ---
.org 0x08091312
    sub  sp, #16
.org 0x08091324
    mov  r2, #16
.org 0x0809134E
    add  sp, #16

; --- 徽章 PrintSaveBadges：栈/后缀窗 +「个」指针（须在图鉴块之前）---
.org 0x0809139A
    sub  sp, #24
.org 0x080913B2
    add  r0, sp, #16
.org 0x080913B8
    mov  r2, #5
.org 0x080913F2
    add  sp, #24
.org 0x08091404
    .word   SuffixGe

; --- 图鉴 PrintSavePokedexCount ---
.org 0x0809140A
    sub  sp, #16
.org 0x0809141C
    mov  r2, #16
.org 0x08091446
    add  sp, #16

; --- 时间 PrintSavePlayTime（push@91454；sub/len/add 相对 +2/+12/+3C）---
.org 0x08091456
    sub  sp, #16
.org 0x08091468
    mov  r2, #16
.org 0x08091492
    add  sp, #16
