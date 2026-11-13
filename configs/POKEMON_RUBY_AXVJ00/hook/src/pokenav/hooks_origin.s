; =============================================================================
; src/pokenav/hooks_origin.s — 领航员复杂钩子 ROM 订址桩（armips 专用）
; ID: P30 tip / P32 列表行 / P33 详情清底 / P34 红条
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

; --- [P33] 训练家之眼进详情：Blank 列表/左栏残墨后拆说明指针---
; AXVJ @ 0x080EBF9C
.org PokeNav_TrainerEye_DetailEnter
    ldr r3, =(PokeNav_TrainerEye_DetailEnter_Hook | 1)
    bx r3
.pool

; --- [P34] 训练家之眼红条标题 DMA 路径（EF558）---
.org PokeNav_TrainerEye_PrintTitle
    ldr r3, =(PokeNav_TrainerEye_PrintTitle_Hook | 1)
    bx r3
.pool

; --- [P34b] 红条标题精灵路径（EF43C，详情实测）---
.org PokeNav_TrainerEye_PrintTitleSprite
    ldr r3, =(PokeNav_TrainerEye_PrintTitleSprite_Hook | 1)
    bx r3
.pool

; --- [P35] 进详情跳过列表行重画（0x080EC364 仅 F23FC 一处调用）---
.org PokeNav_TrainerEye_SkipListRow
    ldr r3, =(PokeNav_TrainerEye_SkipListRow_Hook | 1)
    bx r3
.pool

; --- [P35b] 进详情 case4 跳过左栏统计重画（bl EC2E0 → 双 nop）---
.org PokeNav_TrainerEye_DetailCase4Left
    nop
    nop
; 详情行距：0x080EC060 为 line*2(=16px)。GDB 证实 12px 奇数行 phase=4 叠墨；Middle 同；保持 16px。
