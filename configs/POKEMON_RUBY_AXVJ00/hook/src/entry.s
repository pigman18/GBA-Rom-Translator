@ =============================================================================
@ entry.s — 引擎唯一入口跳板（r0=win 直进 C）。
@ main.asm 在 GameBinAddresses 处贴标签 JP2CHS_Entry 并把 P01 订到此；
@ 链接必须以本文件对象为第一员：game.bin 起点 = EngineEntry。
@
@ 收敛记录（2026-08-24，只 hook PrintNextChar）：
@   Hook3 跳板（GetGlyphTilePointers_Hook/_Orig）→ 移除，
@     CHS 字模取址由 text.c 内部 static GetGlyphTilePointers 承担；
@   WaitArrow_Prepare_Hook → 移除，相位同步折入 text.c static
@     DrawInitialDownArrow（pokeruby text.c 同名）；
@   MapName_DisplayCellLength → 独立域 src/map_name_popup/entry.s。
@ 旧多文件引擎整体归档于 src/bak/text/（不参与构建）。
@ =============================================================================
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global EngineEntry
    .thumb_func
    .type EngineEntry, %function
    .extern PrintNextChar

@ -----------------------------------------------------------------------------
@ 原生帧驱动 call PrintNextChar@0x080032F8（r0=win）直进的引擎入口。
@ PrintNextChar 自管 push {lr}；返回值契约见 src/text.c 头注。
@ -----------------------------------------------------------------------------
EngineEntry:
    ldr r1, =PrintNextChar
    bx  r1
    .pool

.end
