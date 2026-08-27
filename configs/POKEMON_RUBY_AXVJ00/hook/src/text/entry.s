@ =============================================================================
@ entry.s — 引擎唯一入口跳板（r0=win 直进 C）。
@ main.asm 在 GameBinAddresses 处贴标签 JP2CHS_Entry 并把 P01 订到此；
@ 链接必须以本文件对象为第一员：game.bin 起点 = EngineEntry。
@
@ 收敛记录（2026-08-24，只 hook PrintNextChar）：
@   Hook3 跳板（GetGlyphTilePointers_Hook/_Orig）→ 移除，
@     CHS 字模取址由 src/chinese_text.c DecompressGlyph_Chinese 承担；
@   WaitArrow_Prepare_Hook → 移除，相位同步折入 text.c static
@     DrawInitialDownArrow（pokeruby text.c 同名）；
@   GlyphIwtdTramp（P24 InitWindowTileData 跳板）→ 2026-08-25 移除，
@     页游标表落 0x0203FFD2 游戏数据区（背包/队伍死机根因）；
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
    .global PrintNextChar_Origin
    .thumb_func
    .type PrintNextChar_Origin, %function
    .extern PrintNextChar_Hook

@ -----------------------------------------------------------------------------
@ 原生帧驱动 call PrintNextChar@0x080032F8（r0=win）直进的引擎入口。
@ PrintNextChar 自管 push {lr}；返回值契约见 src/text.c 头注。
@ -----------------------------------------------------------------------------
EngineEntry:
    ldr r1, =PrintNextChar_Hook
    bx  r1
    .pool

@ -----------------------------------------------------------------------------
@ PrintNextChar_Origin — 血条/缓冲打印机（tm2）交还官方用。
@
@ 禁止 .incbin 整函数到 0x0880xxxx：函数内 bl（如 → FontFunc / 0x081B12DC）
@ 为 PC 相对，搬家后跳飞 → PC=0x00000004（gdb 进战斗 win=0x020231CC 实证）。
@
@ P01 只盖 8B（ldr+bx+pool @0x080032F8..FF），从 0x08003300 起仍是原指令。
@ 跳板重放被覆盖的 4 条序言，再 bx 回 ROM 续跑（BL 目标正确）。
@ -----------------------------------------------------------------------------
PrintNextChar_Origin:
    push    {r4, lr}
    adds    r4, r0, #0
    ldrh    r0, [r4, #0x14]
    adds    r1, r0, #1
    ldr     r2, =0x08003301
    bx      r2
    .pool
    .size PrintNextChar_Origin, .-PrintNextChar_Origin

.end
