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
    .global GlyphIwtdTramp
    .thumb_func
    .type GlyphIwtdTramp, %function
    .extern PrintNextChar_Hook
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
@ GlyphIwtdTramp — InitWindowTileData 桩（P26）的跳板：
@   1. 全现场入栈（r0-r7+lr；r3 虽为 caller-saved 死值，统一保存省心）
@   2. 调 C 钩 InitWindowTileData_Hook（a0=r0=模板指针，复位页游标）
@   3. 恢复 r0-r7 与 lr
@   4. 重执行被 8B 桩覆盖的 4 条原 prologue 指令（0x2A50-0x2A57）：
@      push {r4-r6,lr}; sub sp,#8; movs r4,r0; lsls r1,r1,#16
@   5. 落回原函数 0x2A58（第 5 条 lsrs r3,r1,#16 起）
@ 原函数体依赖：r4=模板（跨 C 调用存活，AAPCS 保存寄存器）✓
@ -----------------------------------------------------------------------------
GlyphIwtdTramp:
    push    {r0-r7, lr}
    bl      InitWindowTileData_Hook @ bl：lr=下一条|thumb 位 ✓（同 game.bin 内，bl 范围足够；
    @                                    不可用 mov lr,pc+bx——thumb→thumb 时 lr 无 thumb 位，
    @                                    被调函数 bx lr 返回会切进 ARM 态 = Illegal opcode）
    pop     {r0-r7}
    pop     {r3}
    mov     lr, r3
    push    {r4-r6, lr}
    sub     sp, #8
    movs    r4, r0
    lsls    r1, r1, #16
    ldr     r3, =0x08002A59
    bx      r3
    .pool

.end
