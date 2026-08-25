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

; --- [P24] InitWindowTileData 页游标复位（跳板 GlyphIwtdTramp @game.bin）---
; pokeruby: src/text.c InitWindowTileData()；AXVJ @0x08002A50（多帧字库加载
; worker，gdb 采集 2656 命中实证 JP=US 同址）。r0=模板指针, r1=startOffset,
; r2=字模序号。桩覆盖入口 8B（=原 prologue 前 4 条指令，跳板重执行后回
; 0x2A58）；C 钩只复位该 tilemap 的 CHS 页游标（窗体初始化=旧文本作废）。
; ⚠️ 2026-08-25：首版跳板误用 blx（ARMv4T 无此指令=未定义异常死机）已改
;    mov lr,pc+bx 惯用法后重新接入。
.org InitWindowTileData
    ldr r3, =(GlyphIwtdTramp | 1)
    bx r3
.pool
