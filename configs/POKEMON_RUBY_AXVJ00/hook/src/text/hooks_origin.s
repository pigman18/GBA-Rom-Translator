; =============================================================================
; src/text/hooks_origin.s — 文本类复杂钩子的 ROM 订址桩
; armips 专用（main.asm include），不进 gcc；
; 逻辑侧: src/text/entry.s（跳板，编入 game.bin）+ src/text/*_hook.c
; IDs: P01 P02 P04 P05（docs/PATCHES_INVENTORY.md）
; =============================================================================

; --- [P01] 可印字符 -> CHS 引擎；不命中回落官方 FontFuncTable ---
; pokeruby: src/text.c PrintNextChar() 常规字形分支
.org PrintNextChar_RegularGlyph
    ldr r0, =(PrintNextChar_C | 1)
    bx r0
.pool

; --- [P02] Hook3: 字库取址分发（bit15=1 CHS / 0 原函数重定位副本） ---
; pokeruby: src/text.c GetGlyphTilePointers()；r4 为唯一 scratch，先保住调用方 r4
.org GetGlyphTilePointers
    push {r4}
    ldr  r4, =(GetGlyphTilePointers_Hook | 1)
    bx   r4
.pool

; --- [P04] 地图名弹窗旁路：StringLength 位点直跳 MenuPrint(0x0809F6CA) ---
; 跳过 右对齐 pad + 二次 GetMapName(fill=10)。
; ⚠️ 内联 F9 地名 >10B 时原版 10-len 下溢 -> sp+0xFFFE 野写（crash 飞PC 根因）。
; 该路径按字节长度右对齐，与 GetStringWidth 像素宽度无关，勿用宽度钩替代。
; pokeruby: src/map_name_popup.c DrawMapNamePopup()
.org DrawMapNamePopup_StringLength
    ldr r0, =(MapName_DisplayCellLength | 1)
    bx r0
.pool

; --- [P05] 等 A 箭头：CHS 相位前置同步后回落原版主体 0x08003DAD ---
; FA/FB 不经 PrintNextChar；TILE_OFFSET 与 CURSOR 错位 -> 双▼
; pokeruby: src/text.c 等 A 箭头绘制段（AXVJ: DrawInitialDownArrow @0x08003F4C）
.org DrawInitialDownArrow
    ldr r3, =(WaitArrow_Prepare | 1)
    bx r3
.pool
