; =============================================================================
; src/summary/hooks_origin.s — 能力页复杂钩子 ROM 订址桩（armips 专用）
; 逻辑侧: SummaryScreen_PrintMetLevel_* / SummaryScreen_PrintMetDesc_*
; IDs: P27 / P28
; =============================================================================

; --- [P27] 训练家备忘 LvNのとき：清占位后一次打印 Lv+数字+时 ---
; AXVJ 实测 @ 0x0809CFA0（r0-r3 均是实参，跳板必须用 r4/ip）
.org SummaryScreen_PrintMetLevel
    ldr r4, =(SummaryScreen_PrintMetLevel_Hook | 1)
    bx r4
.pool

; --- [P28] 训练家备忘遭遇描述：接管 PrintTrainerMemo 公共打印点 ---
; AXVJ @ 0x0809D1DE（r0=模板已装好；此处改 r1=left/r2=top 后进钩子）
.org SummaryScreen_PrintMetDesc
    mov r1, r6
    mov r2, r9
    ldr r3, =(SummaryScreen_PrintMetDesc_Hook | 1)
    bx r3
.pool
