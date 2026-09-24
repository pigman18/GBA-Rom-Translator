; =============================================================================
; text/hooks_origin.s — PrintNextChar + InitTextPrinter
; 禁止 hook UpdateTilemap：UI 与文字共用，全局重排必撞且无法区分。
; FontFuncTable 不重定向
; =============================================================================

.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool

; [P0x] InitTextPrinter @0x08002C68
; 旧 8B 桩（ldr r4 / bx / pool）致命：
;   1) pool 落在 0x08002C70，盖掉「ldr r4,[sp,#0x18]; mov sb,r4」；
;   2) 跳板却 bx 回 0x08002C71 → 把 pool 当指令执行，sb 永不装 cur_y；
;   3) 用 callee-saved r4 作跳板且未先 push → 返回后调用者 r4 被毁掉
;      （战斗血条 Init 后黑屏卡死，gdb 停在 tpl 0x081BB40C / Lv 打印）。
; 现：12B = 先 push{r4,r5,r6,lr}（保住调用者）+ ldr/bx + pool；
;     跳板补齐 mov sb 序言，从 0x08002C74（movs r4,#0）续跑。
.org InitTextPrinter
    push {r4, r5, r6, lr}
    ldr  r4, =(InitTextPrinter_Hook | 1)
    bx   r4
.pool
