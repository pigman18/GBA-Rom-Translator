@ =============================================================================
@ NickFullName_entry.s — 战斗血条名字：改用 species 查新表拿完整中文名
@
@ ── 问题（BUG-8 根因，2026-11-20 定案）──────────────────────────────────
@ 0x08042408 的战斗血条名字路径：
@
@   08042430  bl GetMonData(mon, 2, sp)   ← param 2 = nickname[10]，只拷 10B
@   08042436  bl StringCopyN(sp, 5)       ← 再截断到 5B（已在本 hook 里 nop 掉）
@   0804243C  → 拼进 0x0202362C
@
@ Gen3 的 nickname 是 10 字节定长字段（+8，紧跟 +18 language / +19 flags），
@ 中文名 3 字 = 12B 塞不下 → 第 3 字被砍成半个。
@
@ ── 解法（照火红 0x08053358 的思路）────────────────────────────────────
@ 火红把「显示名」和「存档 nickname」彻底分开：
@   存档：写 nickname[10]（原版编码）→ 串档不乱
@   显示：species → 指针表 → 完整中文串
@
@ ── 为什么不用 0x0803B11C ────────────────────────────────────────────
@ 0x0803B11C(dst, species) 看着正好，但它内部硬编码：
@   0803B154  cmp r1, #10
@   0803B156  ble  0x803B136      ← 最多拷 11 字节，第 12 字节被写成 FF
@ 3 个调用者共享它（0x08037D06 队伍 / 0x0803FC68 / 0x0811CA60），
@ 直接放宽 cmp 会影响队伍路径（那里 dst 之后紧跟 nickname[10]）。
@
@ 所以本 hook **自己实现拷贝**：r3 = 表基址 + species*24，逐字节到 FF 停。
@ 零共享、零副作用。
@
@ ── 2026-11-20 踩过的坑（务必别重犯）──────────────────────────────────
@ ★ 所有 `ldr r3, =0x08xxxxxx` 必须 `|1`！
@   Thumb 函数地址是偶数，bx 到偶数会让 CPU 切到 ARM 模式 →
@   把 Thumb 字节当 ARM 指令执行 → 乱码跳飞 → mGBA 报
@   "Jumped to invalid address: E3A02004"（那其实是 ARM 的 mov r2,#4）。
@ =============================================================================

    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified

    .global NickFullName_Hook
    .thumb_func
    .type NickFullName_Hook, %function

NickFullName_Hook:
    push {r4, r5, r6, r7, lr}   @ 5 个 = 20B
    sub  sp, #32                @ 局部缓冲 32B（GetMonData 的 dst）

    add  r4, sp, #52            @ r4 = 调用者名字缓冲（20 + 32 = 52）

    @ ① species = GetMonData(mon, MON_DATA_SPECIES=11, localbuf)
    adds r0, r5, #0
    movs r1, #11
    add  r2, sp, #0
    ldr  r3, =0x08039F25        @ ★ |1
    bl   _Nick_bx_r3
    adds r6, r0, #0             @ r6 = species

    @ ② 自己算 src = 新表基址 + species*24
    ldr  r5, =0x09EB0AF4        @ 中文名表（stride 24）
    lsls r0, r6, #1
    adds r0, r0, r6             @ r0 = species*3
    lsls r0, r0, #3             @ r0 = species*24
    adds r7, r5, r0             @ r7 = src

    @ ③ 逐字节拷到 r4，遇 FF 停（含 FF），无长度上限
    movs r5, #0
_Nick_copy:
    ldrb r0, [r7, r5]
    strb r0, [r4, r5]
    adds r5, #1
    cmp  r0, #255
    bne  _Nick_copy
    @ r5 现在 = 已拷字节数（含 FF）

    add  sp, #32
    pop  {r4, r5, r6, r7}
    pop  {r0}
    bx   r0

_Nick_bx_r3:
    bx   r3

    .align 2
    .size NickFullName_Hook, .-NickFullName_Hook
