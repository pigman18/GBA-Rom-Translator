@ =============================================================================
@ PartyMenuDoPrintMonNickname_entry.s — BUG-13
@
@ ★★ 关键 bug（2026-11-23 定位）★★
@ 之前用 `pop {r3}` 把返回地址弹出后丢弃，接着重放 `push {r4,lr}` ——
@ 但此时 lr 是 bl 之后的**假值**（指向 hook 内部），不是调用者的返回地址。
@ 原函数 push {r4,lr} 会把那个假 lr 入栈，函数返回时跳回 hook 内部
@ ⇒ 只执行 1 次就偏离正常流程（GDB 实测：应为 12 次，实际只有 1 次）。
@ 修法：pop 出来的返回地址必须**放回 lr**，再重放 push {r4,lr}。
@ =============================================================================
    .cpu arm7tdmi
    .text
    .align 2
    .thumb
    .syntax unified
    .global PartyMenuDoPrint_Hook
    .thumb_func
    .type PartyMenuDoPrint_Hook, %function

@ 进入：r0=monIndex, r1=b, r2=nameBuffer, sp=S, lr=调用者返回地址
PartyMenuDoPrint_Hook:
    push {r0, r1, r2, r3, r4, lr}   @ 24B → S-24；[sp,#20] = 真 lr

    @ ① 用 nameBuffer 反查中文表（永不命中时 r0=0，走原逻辑）
    ldr  r0, [sp, #8]               @ r0 = nameBuffer
    ldr  r3, =PartyName_LookupJp
    bl   _PdP_bx                    @ r0 = 中文表条目 或 0
    cmp  r0, #0
    beq  _PdP_keep
    str  r0, [sp, #8]               @ 命中：覆盖保存的 r2

_PdP_keep:
    pop  {r0, r1, r2, r3, r4}       @ 20B → S-4；r0/r1 恢复入口值
    pop  {r3}                       @ 4B → S，r3 = 调用者真实返回地址
    mov  lr, r3                     @ ★ 必须放回 lr（见文件头说明）

    @ ② 原样重放被跳板覆盖的 4 条（栈已回到入口状态，lr 已正确）
    push {r4, lr}                   @ 0x0806B288  B510
    sub  sp, #4                     @ 0x0806B28A  B081
    lsls r0, r0, #24                @ 0x0806B28C  0600
    lsls r1, r1, #24                @ 0x0806B28E  0609

    @ ③ 从 0x0806B290 继续（原第 5 条 lsrs r1,r1,#24）
    ldr  r3, =0x0806B291            @ ★ |1
    bx   r3

_PdP_bx:
    bx   r3
    .align 2
    .size PartyMenuDoPrint_Hook, .-PartyMenuDoPrint_Hook
