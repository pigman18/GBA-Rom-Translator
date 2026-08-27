; =============================================================================
; PC 选机菜单（精灵中心「要连接到哪台电脑…」）窗口加宽
;
; pokeruby: src/script_menu.c ScriptMenu_CreatePCMenu
;   ENGLISH 分支默认 width = 8（tile）；Menu_DrawStdWindowFrame(0,0,width+2,…)
; AXVJ: ScriptMenu_CreatePCMenu @ 0x080B0D88（capstone 对 origin ROM 核实）
;   0x080B0DB4  mov r4, #8   — 默认内容宽度 8 tile（框宽 width+2 = 10 tile）
; 中文「真由美的电脑」6 字 × 12px ≈ 9 tile，8 tile 内容区会压到右边框。
; 改为 10 tile 内容（框 12 tile）；玩家名测量更宽时保留，但不低于 10。
; =============================================================================

.org 0x080B0DA4
    cmp     r4, #10
    blt     PCMenuWidthFloor
    b       0x080B0DB6

.org 0x080B0DB4
PCMenuWidthFloor:
    mov     r4, #10
