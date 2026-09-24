; =============================================================================
; src/option/hooks_origin.s — 设置窗口复杂钩子 ROM 订址桩（armips 专用）
; 逻辑侧: src/option/DrawOptionMenuChoice_entry.s + DrawOptionMenuChoice_hook.c
; IDs: P08
; =============================================================================

; --- [P08] 选项高亮：F9 80 短语引用下 dst[2]=style 会指错短语 ---
; 改为打印前写调色板/前景色覆盖变量（见 DrawOptionMenuChoice_hook.c）
; pokeruby: src/option.c DrawOptionMenuChoice()
.org DrawOptionMenuChoice
    push {r3}               ; 保住 style 参数
    ldr r3, =(DrawOptionMenuChoice_Hook | 1)
    bx r3
.pool
