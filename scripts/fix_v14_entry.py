# -*- coding: utf-8 -*-
"""fix_v14_entry.py —— 按 arm7tdmi v4T / GNU as 的实际限制修正 v14 两个跳板。

三条硬限制（本次实测报错原文）：
  1) `pop {r4,r5,r6,lr}`  → Error: cannot honor width suffix
  2) `pop {r4,lr}`        → 同上
     ⇒ v4T 的 Thumb 没有「含 LR 但不含 PC」的多寄存器 POP，只能写 `pop {r4, pc}`。
  3) `mov r1,#4`          → Error: cannot honor width suffix
     ⇒ entry.s 是 **GNU as**（不是 armips），Thumb 下要写 `movs`。
        （`mov` 无后缀只在 armips 那边成立，见 hooks_origin.s 的注释。）

顺带一个简化：std 那一侧**根本不需要 push/pop**——
  钩点在 ⑨b 体内，⑨b 自己的 prologue 已 `push {r4,r5,r6,lr}`，epilogue 会
  `pop {r4,r5,r6}` + `pop {r0}` 还原它们；且 ⑨b 的返回地址取自**它自己栈上**
  那份 lr（`pop {r0}; bx r0`），**不依赖活着的 lr** ⇒ 跳板可以 `bl` 砸 lr、
  也可以随便砸 r4/r5/r6，零栈操作。

一次性脚本；任一处锚点对不上即整体不写盘。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook",
                     "src", "text", "entry.s")

OLD_STD = """\
    cmp     r1, #0                     @ 0 = 池子没发出号
    bne     StdFrameTmap_Resume
    push    {r4, r5, r6, lr}           @ 16B：保 lr，且让 SP 保持 8 对齐（C 调用）
    lsls    r4, r4, #16                @ right  → packed bits 16..23
    lsls    r5, r5, #24                @ bottom → packed bits 24..31
    orrs    r4, r5
    mov     r5, r8                     @ top（已 u8）
    lsls    r5, r5, #8                 @        → packed bits 8..15
    orrs    r6, r5                     @ r6 = left | (top << 8)
    orrs    r6, r4                     @ r6 = packed(left, top, right, bottom)
    adds    r1, r6, #0
    bl      v14_std_frame_erase_C      @ (tilemap = r0, packed = r1)
    pop     {r4, r5, r6, lr}
    ldr     r3, =0x08062165            @ ⑨b epilogue（add sp,#8）—— |1 保 Thumb
    bx      r3
"""

NEW_STD = """\
    cmp     r1, #0                     @ 0 = 池子没发出号
    bne     StdFrameTmap_Resume
    @ 🔴 零栈操作：钩点在 ⑨b 体内，r4/r5/r6 由 ⑨b 自己的 epilogue 从它栈帧还原；
    @    ⑨b 的返回地址也取自它栈上那份 lr（`pop {r0}; bx r0`）⇒ 活 lr 可砸。
    lsls    r4, r4, #16                @ right  → packed bits 16..23
    lsls    r5, r5, #24                @ bottom → packed bits 24..31
    orrs    r4, r5
    mov     r5, r8                     @ top（已 u8）
    lsls    r5, r5, #8                 @        → packed bits 8..15
    orrs    r6, r5                     @ r6 = left | (top << 8)
    orrs    r6, r4                     @ r6 = packed(left, top, right, bottom)
    adds    r1, r6, #0
    bl      v14_std_frame_erase_C      @ (tilemap = r0, packed = r1)；lr 被砸无妨
    ldr     r3, =0x08062165            @ ⑨b epilogue（add sp,#8）—— |1 保 Thumb
    bx      r3
"""

OLD_DLG1 = """\
    push    {r4, lr}                   @ 8B：保 lr，且让 SP 保持 8 对齐
    bl      v14_dlg_frame_erase_C      @ (win = r0, packed = r1)
    pop     {r4, lr}
    bx      lr                         @ 直接回调用者
"""

NEW_DLG1 = """\
    @ ⚠ v4T 的 Thumb 没有 `pop {r4,lr}`（无 32 位 Thumb）⇒ 用含 PC 的形态。
    @   此处 lr **必须**保：桩没碰栈，包装自己的 `push {lr}` 也被跳过，
    @   `pop {r4, pc}` 弹回的正是调用者的返回地址（bit0 = 1，保持 Thumb）。
    push    {r4, lr}                   @ 8B：保 lr + 维持 8 对齐
    bl      v14_dlg_frame_erase_C      @ (win = r0, packed = r1)
    pop     {r4, pc}                   @ 直接回调用者
"""

OLD_DLG2 = """\
    mov     r1, #4                     @ 重放 0x08062670（armips 无 movs 助记符）
"""

NEW_DLG2 = """\
    movs    r1, #4                     @ 重放 0x08062670（entry.s 是 GNU as，须带 s）
"""


def main():
    raw = open(ENTRY, "rb").read()
    crlf = raw.count(b"\r\n")
    text = raw.decode("utf-8").replace("\r\n", "\n")

    reps = [(OLD_STD, NEW_STD), (OLD_DLG1, NEW_DLG1), (OLD_DLG2, NEW_DLG2)]
    problems = []
    for old, new in reps:
        n = text.count(old)
        if n != 1:
            problems.append("锚点命中 %d 次：%r" % (n, old[:50]))
            continue
        text = text.replace(old, new)

    if problems:
        print("=== 失败，未写盘 ===")
        for p in problems:
            print("  ✗", p)
        return 1

    if crlf and crlf == raw.count(b"\n"):
        text = text.replace("\n", "\r\n")

    blob = text.encode("utf-8")
    open(ENTRY, "wb").write(blob)
    print("=== entry.s 修正已落盘：%d → %d B ===" % (len(raw), len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
