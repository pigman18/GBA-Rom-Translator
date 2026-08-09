; =============================================================================
; armips：继续画面单位 + 存档信息框标签拷贝加长
;
; ひき：0x08090FAA → ContinuePokedexUnit_Hook（C 写空串）
;
; 继续菜单徽章「こ」真路径（主菜单 0x08007778）：
;   Menu_PrintText(0x081BC164) @ (0x1A,5) 紧挨数字
;   指针槽 0x080077A0 → 0x081BC164
;
; 存档信息 PrintSaveBadges「こ」：0x080913EE / 0x08389DFA（与继续共用清空）
;
; 存档信息名/图鉴/时间标签：原 memcpy 7～8B + sp#8；中文 F9 00×2 共 9B，
; 截断后无 FF → PrintNextChar 扫栈 → 假名拖尾。徽章一路 copy=9 本就正常。
; B01：见 docs/AXVJ_UI_BUGS.md
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

; 存档信息徽章单位：同样置空
.org ContinueBadgeUnit_CopyLen
    mov r2,0

.org ContinueBadgeUnit_Print
    mov r0,r0
    mov r0,r0

.org ContinueBadgeUnit_String
    .byte 0xFF, 0xFF

.org ContinueBadgeUnit_Ptr
    .word 0x08389DFA

; --- PrintSave* 标签：扩栈 + 拷满 F900 两字 ---
.org PrintSavePlayerName_SubSp
    sub sp, 16
.org PrintSavePlayerName_CopyLen
    mov r2, 16
.org PrintSavePlayerName_AddSp
    add sp, 16

.org PrintSavePokedexCount_SubSp
    sub sp, 16
.org PrintSavePokedexCount_CopyLen
    mov r2, 16
.org PrintSavePokedexCount_AddSp
    add sp, 16

.org PrintSavePlayTime_SubSp
    sub sp, 16
.org PrintSavePlayTime_CopyLen
    mov r2, 16
.org PrintSavePlayTime_AddSp
    add sp, 16
