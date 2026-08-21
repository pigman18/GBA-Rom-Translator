@ =============================================================================
@ text/entry.s — text 类全部地址订钉跳板（.c 只写逻辑，寄存器/lr 约定在这里）。
@ 由 gcc 编入 game.bin；main.asm 仅做 `.org 官方地址 → ldr/bx 符号` 的订址。
@
@ 跳板清单：
@   PrintNextChar                — RegularGlyph 分流（r4=win, r3=char）
@   GetGlyphTilePointers_Hook    — Hook3 分发（栈顶=调用方 r4，lr=官方返回址）
@   GetGlyphTilePointers_Orig    — 原函数整体重定位副本（含字面量池）
@   GetGlyphWidthHook            — GetGlyphWidth 钩（未订 ROM 地址，见 hook.c 头注）
@   GetStringWidthChinese        — pokeruby ABI 适配（r0=win,r1=str→r0=u8）
@   MapName_DisplayCellLength    — 地图名弹窗直跳 MenuPrint
@   WaitArrow_Prepare            — FA/FB 等 A 箭头前置同步
@ =============================================================================
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global PrintNextChar
    .thumb_func
    .type PrintNextChar, %function
    .global FarBxR3
    .thumb_func
    .global GetStringWidthChinese
    .thumb_func
    .type GetStringWidthChinese, %function
    .global MapName_DisplayCellLength
    .thumb_func
    .type MapName_DisplayCellLength, %function
    .global WaitArrow_Prepare
    .thumb_func
    .type WaitArrow_Prepare, %function
    .global GetGlyphTilePointers_Hook
    .thumb_func
    .type GetGlyphTilePointers_Hook, %function
    .global GetGlyphTilePointers_Orig
    .extern PrintNextChar_C
    .extern GetGlyphTilePointers_C
    .extern GetStringWidthChinese_Full
    .extern WaitArrow_Prepare_C

@ -----------------------------------------------------------------------------
@ PrintNextChar：官方 ProcessCurrentChar 常规字形分流点。
@ 入口 r4=win, r3=cur_char, r0 空闲；PrintNextChar_C 返回非 0 表示已消费。
@ -----------------------------------------------------------------------------
PrintNextChar:
    adds r0, r4, #0
    adds r1, r3, #0
    push {r3, r4}
    bl PrintNextChar_C
    pop {r3, r4}
    cmp r0, #0
    beq Pnc_original
    movs r0, #1
    pop {r4}
    pop {r1}
    bx r1

Pnc_original:
    ldr r0, =0x081BB3AC          @ FontFuncTable
    ldrb r1, [r4, #0x0A]
    lsls r1, r1, #2
    adds r1, r1, r0
    ldr r2, [r1]
    adds r0, r4, #0
    adds r1, r3, #0
    ldr r3, =0x081B12DD          @ CallViaR2 | 1
    bl FarBxR3
    movs r0, #1
    pop {r4}
    pop {r1}
    bx r1

FarBxR3:
    bx r3

@ -----------------------------------------------------------------------------
@ Hook3：GetGlyphTilePointers 分发。
@ ROM 桩（main.asm）只做 far-jump 到这里：入口时栈顶=调用方 r4，lr=官方返回址，
@ r0-r3 = 原始参数。C 分发器内部 bl 重定位副本/CHS 解析，返回后按栈还原。
@ -----------------------------------------------------------------------------
GetGlyphTilePointers_Hook:
    push {lr}
    bl   GetGlyphTilePointers_C
    pop  {r0}                    @ r0 = 官方返回址（参数此时已死，可复用）
    pop  {r4}                    @ 还原调用方 r4
    bx   r0

@ 原 GetGlyphTilePointers 整体（0x08003730..0x0800382F 含字面量池）。
@ 跳表绝对字回指原体 handler（除入口外未动），相对跳转位置无关。
.align 2
GetGlyphTilePointers_Orig:
    .incbin "./baserom.gba", 0x3730, 0x100

@ -----------------------------------------------------------------------------
@ GetGlyphWidth 钩：pokeruby ABI (r0=win, r1=glyph → r0=width)。
@ 逻辑在 GetGlyphWidth_hook.c；ROM 订址见该文件头注。
@ -----------------------------------------------------------------------------
    .global GetGlyphWidthHook
    .thumb_func
    .type GetGlyphWidthHook, %function
GetGlyphWidthHook:
    push {r4-r7, lr}
    bl  GetGlyphWidth_C
    pop {r4-r7, pc}

@ pokeruby GetStringWidth ABI: r0=win, r1=str → r0=width（未订 ROM 地址）
GetStringWidthChinese:
    push {lr}
    bl  GetStringWidthChinese_Full
    pop {r1}
    bx r1
    .size GetStringWidthChinese, .-GetStringWidthChinese

@ DrawMapNamePopup @0x0809F67E：StringLength 后直跳 MenuPrint（跳过 pad+二次 fill）
MapName_DisplayCellLength:
    ldr r3, =0x0809F6CB
    bx r3
    .pool
    .size MapName_DisplayCellLength, .-MapName_DisplayCellLength

@ DrawInitialDownArrow @0x08003F4C — 先同步 CHS 游标再进原版主体
WaitArrow_Prepare:
    push {r0, lr}
    bl  WaitArrow_Prepare_C
    pop {r0, r3}
    movs r1, #0
    strh r1, [r0, #6]
    push {r3}
    ldr r3, =0x08003DAD
    bl FarBxR3
    pop {r1}
    bx r1
    .pool
    .size WaitArrow_Prepare, .-WaitArrow_Prepare

.end
