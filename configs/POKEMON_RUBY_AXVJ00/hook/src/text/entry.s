@ =============================================================================
@ text/entry.s — v6：PrintNextChar 入口 + InitTextPrinter 块边界钩
@ UpdateTilemap_Origin = 直调完整原生 @0x080036DC（供中文打印层使用）
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
    .global UpdateTilemap_Origin
    .thumb_func
    .type UpdateTilemap_Origin, %function
    .global InitTextPrinter_Hook
    .thumb_func
    .type InitTextPrinter_Hook, %function
    .extern PrintNextChar_Hook
    .extern InitTextPrinter_hook_C

EngineEntry:
    ldr r1, =PrintNextChar_Hook
    bx  r1
    .pool

@ P01 盖 8B（ldr+bx+pool @0x080032F8..FF）；从 0x08003300 起仍是原指令。
PrintNextChar_Origin:
    push    {r4, lr}
    adds    r4, r0, #0
    ldrh    r0, [r4, #0x14]
    adds    r1, r0, #1
    ldr     r2, =0x08003301
    bx      r2
    .pool
    .size PrintNextChar_Origin, .-PrintNextChar_Origin

@ 完整原生 UpdateTilemap（未劫 ROM）；中文打印层专用。
UpdateTilemap_Origin:
    ldr     r3, =0x080036DD
    bx      r3
    .pool
    .size UpdateTilemap_Origin, .-UpdateTilemap_Origin

@ [P0x] InitTextPrinter 块边界钩跳板。
@ 入口约定（ROM 桩 @InitTextPrinter 已用 r12 转跳，参数寄存器原样）：
@   r0=win  r1=text  r2=tile_base  r3=cur_x  [sp+0x18]=cur_y(第5参数)
@   入口尚未 push（r4-r8/sb/lr 全是调用者的），sp = 调用者 sp。
@ 被覆盖的 8B 原指令 = push{r4,r5,r6,lr} + mov r6,sb + mov r5,r8 + push{r5,r6}，
@   即重放后 sp -= 24，cur_y 移到 [sp+0x18]（与本体读它的一致）。
@ C 钩 InitTextPrinter_hook_C(win, tile_base, cur_x, cur_y) —— 只读不改 win，
@   复位 ChsPhase 相位；r2/r3 传参后本体还要用，须恢复。
@ 返回跳回 0x08002C70（本体 ldr r4,[sp,#0x18] 读 cur_y 继续）。
InitTextPrinter_Hook:
    push    {r4, r5, r6, lr}       @ 重放原指令1
    mov     r6, sb                 @ 原指令2
    mov     r5, r8                 @ 原指令3
    push    {r5, r6}               @ 原指令4  → sp 已 -24，cur_y @[sp+0x18]
    @ 保存 r0-r3 原值（C 会破坏 r1-r3，本体后续还要用 r2/r3）
    push    {r0, r1, r2, r3}       @ sp 再 -16
    ldr     r4, [sp, #0x28]        @ cur_y：原 [sp+0x18] 现 +16 = +0x28
    @ 重排 C 参数：r0=win(不变), r1=tile_base, r2=cur_x, r3=cur_y
    adds    r1, r2, #0             @ r1 = tile_base（thumb 禁低寄存器间 mov）
    adds    r2, r3, #0             @ r2 = cur_x
    adds    r3, r4, #0             @ r3 = cur_y
    push    {lr}                   @ 保返回地址（bl 会改 lr）
    bl      InitTextPrinter_hook_C
    pop     {r4}                   @ r4 = 返回地址
    pop     {r0, r1, r2, r3}       @ 恢复 r0-r3 原值
    @ 跳回本体 0x08002C70（thumb 位）
    ldr     r5, =0x08002C71
    bx      r5
    .pool
    .size InitTextPrinter_Hook, .-InitTextPrinter_Hook

.end
