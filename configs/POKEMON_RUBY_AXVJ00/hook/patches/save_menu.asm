; =============================================================================
; [P40] 存档确认信息框标签：扩大 sub sp + memcpy CopyLen
;
; 日版 PrintSave* 定长 memcpy 进 8B 栈（玩家/时间 CopyLen=7，图鉴=8），
; 重定位 F7 译文含 FF 共 9B → 截断无终止符 → 打印跑飞 + 右屏铺砖。
; 徽章本就 stack=16 / CopyLen=9，不动。
; 详见 docs/research/SAVE_MENU_CORRUPTION.md
; =============================================================================

; --- 玩家 PrintSavePlayerName：sub #8→#16，CopyLen 7→16，add #8→#16 ---
.org 0x08091312
    sub  sp, #16
.org 0x08091324
    mov  r2, #16
.org 0x0809134E
    add  sp, #16

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
