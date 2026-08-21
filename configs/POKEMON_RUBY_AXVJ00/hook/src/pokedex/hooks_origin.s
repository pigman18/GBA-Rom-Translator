; =============================================================================
; src/pokedex/hooks_origin.s — 图鉴复杂钩子 ROM 订址桩（armips 专用）
; 逻辑侧: src/pokedex/UnusedPrintMonName_entry.s + UnusedPrintMonName_hook.c
; IDs: P07
; =============================================================================

; --- [P07] 图鉴条目屏分类名行：拼接分类+宝可梦短语流一次打印 ---
; pokeruby: src/pokedex.c 条目页分类名行打印（美版静态函数，AXVJ 自命名）
.org UnusedPrintMonName
    ldr r3, =(UnusedPrintMonName_Hook | 1)
    bx r3
.pool
