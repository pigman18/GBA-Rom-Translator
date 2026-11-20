@ =============================================================================
@ NickSlot_entry.s — 遭遇文本「野生的XXX」：用 species 查新表写完整名
@
@ ── 静态证据链（2026-11-20，一次查清）────────────────────────────────
@ 遭遇模板 0x1420F0C：
@   f7 00 0f 00 | f7 00 0b d8 | f7 00 03 0b | FD 03 | f7 00 0d 02 | f7 00 02 78 |
@   野            生            的            展开     跳            出
@   f7 00 08 29 | f7 00 08 9e | 3C | FB | FF
@   来            了             !    换行  结束
@
@ FD 03 的展开代码在 0x0811C790 起的函数（由 GDB watch 0x0202363D 抓到
@ PC=0x0811C85E / LR=0x0811C7B4 定位）：
@
@   0811C798  ldr r2, [pc]        ; 0x02015E60（战斗槽索引表）
@   0811C79A  adds r0, r5, r2
@   0811C79C  ldrb r1, [r0, #0]   ; r1 = 槽索引
@   0811C79E  movs r0, #100
@   0811C7A0  muls r0, r1         ; idx * 100
@   0811C7A2  ldr r1, [pc]        ; 0x03004290
@   0811C7A4  adds r0, r0, r1     ; r0 = &gBattleMons[idx]
@   0811C7A6  movs r1, #2         ; MON_DATA_NICKNAME
@   0811C7A8  mov  r2, sp
@   0811C7AA  bl   0x08039F24     ; GetMonData(mon, 2, sp)  ← 本 hook
@   0811C7AE  mov  r0, sp
@   0811C7B0  bl   0x08004290     ; StringCopyN(sp, 5)       ← 截断
@   0811C7B4  mov  r4, sp         ; 名字源
@   0811C84A  ... 逐字节拷到 buffer，遇 FF 停，无上限
@
@ ── 为什么只扩上限不行 ──────────────────────────────────────────────
@ nickname[10] 是 Gen3 存档定长字段，中文 3 字 = 12B 塞不下，
@ 第 3 字只写进半个（实测 f7 00 01 02），后面 75 53 57 是越界残渣。
@ 把 0x08004290 的上限从 5 改到 13，只是把残渣也搬进来 →
@ 屏幕上出现「落雷 ゝ乱」这种断字。
@ 必须先换数据源。
@
@ ── 本 hook ───────────────────────────────────────────────────────
@ 替换 0x0811C7AA 那条 bl（GetMonData(mon, 2, sp)）：
@   species = GetMonData(mon, 11, tmp)
@   从新表 0x1EB0AF4 + species*24 拷完整中文名（自带 FF）到 sp
@ 后续 StringCopyN 遇 FF 即停，不会截断；nickname[10] 一字节不动。
@
@ ── 寄存器（进入时）────────────────────────────────────────────────
@   r0 = mon 指针, r1 = 2(MON_DATA_NICKNAME), r2 = sp = 目标缓冲
@
@ ── 铁律 ──────────────────────────────────────────────────────────
@ 所有 ldr r3, =0x08xxxxxx 必须 |1（Thumb 位）。
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global NickSlot_Hook
    .thumb_func
    .type NickSlot_Hook, %function

NickSlot_Hook:
    push {r4, r5, r6, lr}       @ 16B
    sub  sp, #32                @ 局部缓冲 32B（0x08039FC0 解字段需要足够空间）

    adds r4, r0, #0             @ r4 = mon
    adds r5, r2, #0             @ r5 = dst（调用者 sp）
    mov  r6, r9                 @ 保存 r9（0x0811C84E 之后要用，保险）

    @ ① species = GetMonData(mon, MON_DATA_SPECIES=11, localbuf)
    adds r0, r4, #0
    movs r1, #11
    add  r2, sp, #0
    ldr  r3, =0x08039F25        @ ★ |1
    bl   _Ns_bx_r3

    @ ② 范围检查 1..411
    cmp  r0, #1
    blt  _Ns_fallback
    movs r1, #206
    lsls r1, r1, #1             @ 412
    cmp  r0, r1
    bge  _Ns_fallback

    @ ③ src = 0x1EB0AF4 + species*24
    ldr  r3, =0x09EB0AF4
    lsls r1, r0, #1
    adds r1, r1, r0             @ species*3
    lsls r1, r1, #3             @ species*24
    adds r3, r3, r1

    @ ④ 拷到 r5，遇 FF 停（含 FF）
    movs r1, #0
_Ns_copy:
    ldrb r0, [r3, r1]
    strb r0, [r5, r1]
    adds r1, #1
    cmp  r0, #255
    bne  _Ns_copy

    mov  r9, r6                 @ 恢复 r9
    add  sp, #32
    pop  {r4, r5, r6}
    pop  {r0}
    bx   r0

_Ns_fallback:
    @ 原逻辑：GetMonData(mon, 2, dst)
    adds r0, r4, #0
    movs r1, #2
    adds r2, r5, #0
    ldr  r3, =0x08039F25        @ ★ |1
    bl   _Ns_bx_r3
    mov  r9, r6                 @ 恢复 r9
    add  sp, #32
    pop  {r4, r5, r6}
    pop  {r0}
    bx   r0

_Ns_bx_r3:
    bx   r3

    .align 2
    .size NickSlot_Hook, .-NickSlot_Hook
