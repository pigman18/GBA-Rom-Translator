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
    .global EngineIwtdEntry
    .thumb_func
    .type EngineIwtdEntry, %function
    .global InitWindowTileData_Origin
    .thumb_func
    .type InitWindowTileData_Origin, %function
    .extern InitWindowTileData_Hook

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

@ -----------------------------------------------------------------------------
@ [P24] InitWindowTileData 入口（v9 削字库）—— 见 main.asm / hooks_origin.s。
@ 原生签名 void InitWindowTileData(tpl, u16 startOffset, u8 glyph)：
@   r0=tpl  r1=startOffset(u16)  r2=glyph(u8)
@   → 写 tileData + (startOffset + glyph*2) 两格（upper/lower），256 次铺满
@     charblock（tile [1,513)）。C 侧拦掉落在中文区的字形以腾出 tile。
@
@ P24 覆盖入口 8B（0x08002A50..57），被盖掉的 4 条序言在 Origin 桩里重放，
@ 再 bx 回 0x08002A58。原生尾声 add sp,#8; pop{r4-r6}; pop{r0}; bx r0
@ 会把我们压入的 lr 弹到 r0 并正确返回 C 调用方。
@
@ ⚠ 暂存寄存器只能用 **r3**，绝不能碰 r0/r1/r2：
@   r0=tpl / r1=startOffset / r2=glyph 全是实参，而 0x08002A58 起立刻要用
@   r1(>>16) 与 r2(&0xFF)。首版拿 r1(P24 覆盖指令) / r2(Origin 跳转) 当
@   `ldr =addr` 暂存 → 256 次预渲染全画成同一个字形且落在错误起点，
@   整本字库等于全空（实测：值列的 ＬＲ / ７ 全部透明）。
@   r3 是 caller-saved，可安全占用。
@ -----------------------------------------------------------------------------
EngineIwtdEntry:
    ldr r3, =InitWindowTileData_Hook
    bx  r3
    .pool
    .size EngineIwtdEntry, .-EngineIwtdEntry

InitWindowTileData_Origin:
    push    {r4, r5, r6, lr}
    sub     sp, #8
    adds    r4, r0, #0
    lsls    r1, r1, #0x10
    ldr     r3, =0x08002A59
    bx      r3
    .pool
    .size InitWindowTileData_Origin, .-InitWindowTileData_Origin

.end
