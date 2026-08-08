; =============================================================================
; armips：继续画面单位
;
; ひき：0x08090FAA → ContinuePokedexUnit_Hook（C 写空串）
;
; 继续菜单徽章「こ」真路径（主菜单 0x08007778）：
;   Menu_PrintText(0x081BC164) @ (0x1A,5) 紧挨数字
;   指针槽 0x080077A0 → 0x081BC164
; 此前误改的 0x08389DFA / 0x08091394 是另一路（训练家卡式），不是本屏。
; =============================================================================

.thumb

.org ContinuePokedexUnit_Append
    ldr r0, =(ContinuePokedexUnit_Hook | 1)
    bx r0
.pool

; 继续菜单：跳过单位 Menu_PrintText
.org ContinueMenuBadgeUnit_Print
    mov r0,r0
    mov r0,r0

; 继续菜单：こ 正文置空（勿 relocate 指针 0x080077A0，曾打飞菜单）
.org ContinueMenuBadgeUnit_String
    .byte 0xFF, 0xFF

; 另一路（0x08091394）仍置空，避免训练家卡等处残留
.org ContinueBadgeUnit_CopyLen
    mov r2,0

.org ContinueBadgeUnit_Print
    mov r0,r0
    mov r0,r0

.org ContinueBadgeUnit_String
    .byte 0xFF, 0xFF

.org ContinueBadgeUnit_Ptr
    .word 0x08389DFA
