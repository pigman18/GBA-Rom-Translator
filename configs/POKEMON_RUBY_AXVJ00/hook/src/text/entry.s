@ =============================================================================
@ text/entry.s — PrintNextChar 入口 + InitTextPrinter 块边界钩
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

@ [P0x] InitTextPrinter 块边界钩。
@ ROM 桩已 push{r4,r5,r6,lr}（真·调用者寄存器），再 ldr/bx 至此。
@ 此处补齐被 pool 盖掉的序言后半 + C 钩，再从 0x08002C74 续跑。
@ 原序言：
@   C68 push{r4,r5,r6,lr}   ← 桩已做
@   C6A mov r6,sb / C6C mov r5,r8 / C6E push{r5,r6}
@   C70 ldr r4,[sp,#0x18] / C72 mov sb,r4   ← 被 pool 覆盖，必须在此重放
@   C74 movs r4,#0 起完好 ← 跳回点
InitTextPrinter_Hook:
    mov     r6, sb
    mov     r5, r8
    push    {r5, r6}               @ 与原 C6E 对齐；此后 cur_y 在 [sp,#0x18]
    push    {r0, r1, r2, r3}       @ 保参（C 会砸 r1-r3）
    ldr     r4, [sp, #0x28]        @ cur_y：0x18 + 16
    adds    r1, r2, #0             @ r1 = tile_base
    adds    r2, r3, #0             @ r2 = cur_x
    adds    r3, r4, #0             @ r3 = cur_y
    bl      InitTextPrinter_hook_C
    pop     {r0, r1, r2, r3}
    ldr     r4, [sp, #0x18]        @ 重放被盖掉的 ldr
    mov     sb, r4                 @ 重放 mov sb,r4
    ldr     r5, =0x08002C75        @ 续跑 movs r4,#0
    bx      r5
    .pool
    .size InitTextPrinter_Hook, .-InitTextPrinter_Hook

.end
