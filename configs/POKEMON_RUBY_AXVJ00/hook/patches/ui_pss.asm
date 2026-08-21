; =============================================================================
; [P17 P18] PSS 右上角 B 图标列左移（纯值）
; pokeruby: src/pokemon_summary_screen.c 头部布局（AXVJ: PrintSummaryWindowHeaderText @0x0809D5D4）
; 原布局 tile[24][25] 画 B 图标；中文「取消/替换」反向增长会踩图标 -> 左移一列
; =============================================================================

.org 0x0809D60C
    mov r1, 0x17            ; PlaceTextTile_White(5,x,0) 原 0x18 -> tile 列 23

.org 0x0809D616
    mov r1, 0x18            ; PlaceTextTile_White(6,x,0) 原 0x19 -> tile 列 24
