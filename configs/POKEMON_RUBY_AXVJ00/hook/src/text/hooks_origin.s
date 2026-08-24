; =============================================================================
; src/text/hooks_origin.s — 文本类复杂钩子的 ROM 订址桩
; armips 专用（main.asm include），不进 gcc；
; 逻辑侧: src/text/entry.s（跳板，编入 game.bin）+ src/text/*_hook.c
; IDs: P01 P02 P04 P05（docs/PATCHES_INVENTORY.md）
; =============================================================================

; --- [P01] 全面接管：原生 PrintNextChar 整函数替换（零回落，Phase C 换装） ---
; pokeruby: src/text.c PrintNextChar()；AXVJ @0x080032F8（含 FA-FF 控制码跳表）。
; r0=win 按 AAPCS 原样进 C；r1 为 caller-saved 可作转跳暂存。
; 引擎返回值契约：可印=1 / FF=0 / FA·FB·FD·FE=2 / FC=子结果（docs/ruby_jp_text.md）。
.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool

; --- [P02] Hook3: 字库取址分发（bit15=1 CHS / 0 原函数重定位副本） ---
; pokeruby: src/text.c GetGlyphTilePointers()；r4 为唯一 scratch，先保住调用方 r4
.org GetGlyphTilePointers
    push {r4}
    ldr  r4, =(GetGlyphTilePointers_Hook | 1)
    bx   r4
.pool

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

; --- [P05] 等 A 箭头：CHS 相位前置同步后回落原版主体 0x08003DAD ---
; FA/FB 不经 PrintNextChar；TILE_OFFSET 与 CURSOR 错位 -> 双▼
; pokeruby: src/text.c 等 A 箭头绘制段（AXVJ: DrawInitialDownArrow @0x08003F4C）
.org DrawInitialDownArrow
    ldr r3, =(WaitArrow_Prepare_Hook | 1)
    bx r3
.pool
