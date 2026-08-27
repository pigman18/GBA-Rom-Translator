; =============================================================================
; map_name_popup/hooks_origin.s — 地名弹窗居中钩 ROM 订址桩
; armips 专用（main.asm include），不进 gcc；
; 逻辑侧: map_name_popup/entry.s（跳板）+ map_name_popup/MapNamePopup_hook.c
; ID: P04（docs/PATCHES_INVENTORY.md）
; =============================================================================

; --- [P04] 地名弹窗居中：StringLength 位点(0x0809F67E)接管 → MapNamePopup_CalcLeftPx ---
; 原生按字节数在 10 格字段居中，内联 F9 地名 >10B 时 10-len 下溢 ->
; sp+0xFFFE 野写（历史 crash 飞PC 根因）；旧方案直跳 MenuPrint 止血但居左。
; 现 C 钩按本引擎真实步进（空白/字面量 8px、汉字 12px）算留白并加大
; MenuPrint 的 x 起点（8px/格，不动 20B 缓冲区）；越界返回 0 维持原位。
; 落点 0x0809F6CE（跳过 movs r1,#1）。pokeruby 参照: Text_InitWindow_Centered。
.org DrawMapNamePopup_StringLength
; 只用 r3 转跳：native 0809F67C `mov r0,sp` 的缓冲区指针必须原样进钩子
    ldr r3, =(MapName_DisplayCellLength | 1)
    bx r3
.pool
