; =============================================================================
; hooks_origin.s — 文本引擎 ROM 订址桩（armips 专用，main.asm include，不进 gcc）
; 逻辑侧: src/entry.s（入口跳板，gcc 编入 game.bin）+ src/text.c
; IDs: P01（docs/PATCHES_INVENTORY.md）
;
; 2026-08-24 收敛：只 hook PrintNextChar，全面接管日版文字打印——
;   P02 Hook3 / P05 等 A 箭头前置同步 已移除（见 PATCHES_INVENTORY.md 台账）；
;   P04 地名弹窗居中独立为 src/map_name_popup/hooks_origin.s。
; =============================================================================

; --- [P01] 全面接管：原生 PrintNextChar 整函数替换 ---
; pokeruby: src/text.c PrintNextChar()；AXVJ @0x080032F8（含 FA-FF 控制码跳表）。
; r0=win 按 AAPCS 原样进 C；r1 为 caller-saved 可作转跳暂存。
; 返回值契约：可印=1 / FF=0 / FA·FB·FD·FE=2 / FC=子结果。
.org PrintNextChar
    ldr r1, =(JP2CHS_Entry | 1)
    bx r1
.pool
