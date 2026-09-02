; =============================================================================
; text/hooks_origin.s — v6：PrintNextChar + InitTextPrinter
; 禁止 hook UpdateTilemap：UI 与文字共用，全局重排必撞且无法区分。
; 中文在 PrintNextChar→PrintGlyph 内预渲染后直调 UpdateTilemap_Origin。
; FontFuncTable 不重定向
; =============================================================================

.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool

; [P0x] InitTextPrinter：文本块开始边界。r0-r3 全被参数占用（win/text/
; tile_base/cur_x），第5参数 cur_y 在 [sp+0x18]（入口未 push，仍在调用者栈）。
; 用 r4 转跳：r4 非参数，且本体首句 push {r4,r5,r6,lr} 即保存入口值、
; 调用者（wrapper）返回后自会重赋 r4，破坏无碍。armips thumb ldr 不支持 r12。
; 覆盖前 8B（B570 464E 4645 B460），跳板 entry.s 重放后再跳回 0x08002C70。
.org InitTextPrinter
    ldr r4, =(InitTextPrinter_Hook | 1)
    bx r4
.pool
