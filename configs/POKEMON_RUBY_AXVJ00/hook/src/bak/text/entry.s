@ =============================================================================
@ text/entry.s — text 类全部地址订钉跳板（.c 只写逻辑，寄存器/lr 约定在这里）。
@ 由 gcc 编入 game.bin；main.asm 仅做 `.org 官方地址 → ldr/bx 符号` 的订址。
@
@ 跳板清单（2026-08-23 Phase C 换装后）：
@   EngineEntry                  — 引擎入口（= game.bin 起点，r0=win 直进 C）
@   GetGlyphTilePointers_Hook    — Hook3 分发（栈顶=调用方 r4，lr=官方返回址）
@   GetGlyphTilePointers_Orig    — 原函数整体重定位副本（含字面量池）
@   MapName_DisplayCellLength    — 地名弹窗居中钩（MapNamePopup_hook.c，容量10格）
@   WaitArrow_Prepare_Hook      — FA/FB 等 A 箭头前置同步
@ （旧 PrintNextChar r4/r3→r0/r1 编组 + FontFunc 回落跳板已随全面接管移除。）
@ =============================================================================
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global EngineEntry
    .thumb_func
    .type EngineEntry, %function
    .global FarBxR3
    .thumb_func
    .global MapName_DisplayCellLength
    .thumb_func
    .type MapName_DisplayCellLength, %function
    .global WaitArrow_Prepare_Hook
    .thumb_func
    .type WaitArrow_Prepare_Hook, %function
    .global GetGlyphTilePointers_Hook
    .thumb_func
    .type GetGlyphTilePointers_Hook, %function
    .global GetGlyphTilePointers_Orig
    .extern PrintNextChar
    .extern GetGlyphTilePointers_C
    .extern MapNamePopup_CalcLeftPx
    .extern WaitArrow_Prepare

@ -----------------------------------------------------------------------------
@ EngineEntry：原生帧驱动 call PrintNextChar@0x080032F8（r0=win）直进的引擎入口。
@ main.asm 在 GameBinAddresses 处贴标签 JP2CHS_Entry 并把 P01 订到此。
@ 尾跳 C：PrintNextChar 自管 push {lr}；返回值契约见 text_jp2chs.c 头注。
@ -----------------------------------------------------------------------------
EngineEntry:
    ldr r1, =PrintNextChar
    bx  r1
    .pool

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
@ DrawMapNamePopup @0x0809F67E（原 bl StringLength 位点）：
@ native 0809F67C `mov r0,sp` 已把 20B 缓冲区放入 r0；ROM 补丁只用 r3 转跳
@ （严禁 ldr r0 —— v1~v3 历史根因：覆盖 r0 后 C 把跳板自身机器码当名字量宽）。
@ r5=地图头指针必须保活（C 按 AAPCS 自动保 r5）。
@ C 侧按引擎真实步进算居中留白（只读），返回留白 px；跳板注入
@ r1 = 原生 x 基准 1 + 留白px（curX 像素语义，见 MapNamePopup_hook.c 头注）。
@ 落点 0x0809F6CE 跳过 movs r1,#1，其后 bl MenuPrint 自设 lr。
@ -----------------------------------------------------------------------------
MapName_DisplayCellLength:
    push {r0, lr}                 @ r0=缓冲区指针必须保活
    bl   MapNamePopup_CalcLeftPx
    adds r2, r0, #0               @ 留白 px 暂存（thumb 禁低寄存器间 mov）
    pop  {r0, r3}                 @ r0=缓冲区（MenuPrint 参数），r3=官方返回址弃
    movs r1, #1                   @ 原生 x 基准（=1px）
    adds r1, r1, r2               @ x = 1 + 留白px
    ldr  r3, =0x0809F6CF          @ 落点 0x0809F6CE (movs r2,#1) | thumb
    bx   r3
    .pool
    .size MapName_DisplayCellLength, .-MapName_DisplayCellLength

@ DrawInitialDownArrow @0x08003F4C — 先同步 CHS 游标再进原版主体
WaitArrow_Prepare_Hook:
    push {r0, lr}
    bl  WaitArrow_Prepare
    pop {r0, r3}
    movs r1, #0
    strh r1, [r0, #6]
    push {r3}
    ldr r3, =0x08003DAD
    bl FarBxR3
    pop {r1}
    bx r1
    .pool
    .size WaitArrow_Prepare_Hook, .-WaitArrow_Prepare_Hook

.end
