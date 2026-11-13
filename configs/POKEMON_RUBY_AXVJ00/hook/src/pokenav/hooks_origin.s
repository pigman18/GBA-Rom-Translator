; =============================================================================
; src/pokenav/hooks_origin.s — 领航员复杂钩子 ROM 订址桩（armips 专用）
; ID: P30 tip / P32 列表行拼接
; 注意：P31 左侧 bg 已改为 grid_bg 按 tpl@0x081BB7B4 透明，无 ROM 订址、无 .bss 锁
; =============================================================================

; --- [P30] 主菜单 tip：BlankWindowRect 后 Menu_PrintText(str,4,17) ---
; AXVJ @ 0x080EA6C8（r0=kind, r1=index）
.org PokeNav_PrintMenuTip
    ldr r3, =(PokeNav_PrintMenuTip_Hook | 1)
    bx r3
.pool

; --- [P32] 训练家之眼列表行：像素列垫 class 后再拼 name ---
; AXVJ @ 0x080F228C（r0=dest, r1=index）
.org PokeNav_TrainerEye_FormatListLine
    ldr r3, =(PokeNav_TrainerEye_FormatListLine_Hook | 1)
    bx r3
.pool
