; =============================================================================
; text/hooks_origin.s — v6：仅 P01 PrintNextChar
; 禁止 hook UpdateTilemap：UI 与文字共用，全局重排必撞且无法区分。
; 中文在 PrintNextChar→PrintGlyph 内预渲染后直调 UpdateTilemap_Origin。
; FontFuncTable 不重定向
; =============================================================================

.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool
