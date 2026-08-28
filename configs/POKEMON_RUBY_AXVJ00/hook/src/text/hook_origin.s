; =============================================================================
; hooks_origin.s — 文本引擎 ROM 订址桩（armips 专用，main.asm include，不进 gcc）
; 逻辑侧: src/entry.s（入口跳板，gcc 编入 game.bin）+ src/text.c
; IDs: P01（docs/PATCHES_INVENTORY.md）
;
; 2026-08-24 收敛：只 hook PrintNextChar，全面接管日版文字打印——
;   P02 Hook3 / P05 等 A 箭头前置同步 已移除（见 PATCHES_INVENTORY.md 台账）；
;   P04 地名弹窗居中独立为 src/map_name_popup/hooks_origin.s；
;   P24 旧用途（InitWindowTileData 页游标复位，页表落 0x0203FFD2 游戏数据区 =
;   背包/队伍死机根因，PC=0x00000004 实证）→ 2026-08-25 移除；
;   **P24 于 2026-08-29 复用为"削字库"入口**（字模落 VRAM 抢地盘的根治），
;   不再动页表、不占 0x0203FFD2。
; =============================================================================

; --- [P01] 全面接管：原生 PrintNextChar 整函数替换 ---
; pokeruby: src/text.c PrintNextChar()；AXVJ @0x080032F8（含 FA-FF 控制码跳表）。
; r0=win 按 AAPCS 原样进 C；r1 为 caller-saved 可作转跳暂存。
; 返回值契约：可印=1 / FF=0 / FA·FB·FD·FE=2 / FC=子结果。
.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool

; --- [P24] InitWindowTileData 入口接管（v9, 2026-08-29） ---
; 背景：tm1 是"ROM 预渲染"模式，原生不写 VRAM；InitWindowTileData 分 256 次
;   把整本字库铺进 tile [1,513)（tile = startOffset + glyph*2，每字形 2 tile）。
;   中文字形要落 VRAM 就必然和字库抢地盘——这就是"为什么有 tile 限制"。
; 现状：**跳过逻辑已停用**（时序实证：预渲染整个跑在文本打印之前，不会覆盖
;   中文；跳过反而把菜单要用的字形删成空白）。钩子现为直通，保留以便日后恢复。
;   中文改为避开已实测引用的字形 tile，见 FontFunc_hook.c 的 TM1_ROW_TAB。
;
; ⚠ **暂存只能用 r3**：本处覆盖的是函数最开头 8B，r0/r1/r2 是三个实参
;   (tpl / startOffset / glyph)，0x08002A58 起立刻要用。首版用 r1 →
;   startOffset 被冲成跳板地址，256 次预渲染落点全错、字库全空。
.org InitWindowTileData
    ldr r3, =(EngineIwtdEntry | 1)
    bx r3
.pool
