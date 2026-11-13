; =============================================================================
; src/summary/hooks_origin.s — 能力页复杂钩子 ROM 订址桩（armips 专用）
; 逻辑侧: PrintTrainerMemo_* / NameLayoutTiles_*
; IDs: P27 / P29（旧 P28 MetDesc 重拼已并入 P27）
; =============================================================================

; --- [P27] 训练家备忘整段：性格名 + Lv时在…遇到（GetStringWidth 排「性格」）---
; AXVJ @ 0x0809D03C（r0=mon, r1=left, r2=top）
.org SummaryScreen_PrintTrainerMemo
    ldr r3, =(SummaryScreen_PrintTrainerMemo_Hook | 1)
    bx r3
.pool

; --- [P29] 能力页物种名旁 ♂/♀：从 bl StringLength 起按像素宽算格 ---
; 原 @ 0x0809D256；D230..D254 与 D274 物种名表字面量留给 patch-table
; 进入时 r0=name（D254 adds r0,r4）、r5=mon
.org SummaryScreen_NameLayoutTiles
    mov r1, r5
    ldr r3, =(SummaryScreen_NameLayoutTiles_Hook | 1)
    bl SummaryScreen_NameLayoutTiles_via
    b SummaryScreen_NameLayoutTiles_Epilogue
SummaryScreen_NameLayoutTiles_via:
    bx r3
.pool
