; =============================================================================
; src/pokenav/hooks_origin.s — 领航员复杂钩子 ROM 订址桩（armips 专用）
; 逻辑侧: PokeNav_PrintMenuTip_*
; ID: P30
; =============================================================================

; --- [P30] 主菜单 tip：BlankWindowRect(3,17,28,18) 后 Menu_PrintText(str,4,17) ---
; AXVJ @ 0x080EA6C8（r0=kind, r1=index）
.org PokeNav_PrintMenuTip
    ldr r3, =(PokeNav_PrintMenuTip_Hook | 1)
    bx r3
.pool
