; =============================================================================
; text/hooks_origin.s — PrintNextChar 订址桩（2026-09-22 · v1 8px 渲染层）
;
; 只装一个钩子：PrintNextChar@0x080032F8 → EngineEntry（entry.s，game.bin 首地址）。
; 盖掉 8B（push {r4,lr} / adds r4,r0,#0 / ldrh r0,[r4,#0x14] / adds r1,r0,#1），
; entry.s 的 PrintNextChar_Origin 逐条重放后从 0x08003300 续跑。
;
; 不再挂 InitTextPrinter：
;   v13~v16 挂它只为了「按串复位分配器」。v1 的发号是**粘性字→槽**，
;   字与串无关、复画原地覆写即幂等 ⇒ 不需要任何复位信号，钩子越少越好。
; 禁止 hook UpdateTilemap：UI 与文字共用，全局重排必撞。
; =============================================================================

.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool
