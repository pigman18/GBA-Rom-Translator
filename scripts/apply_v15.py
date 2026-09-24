# -*- coding: utf-8 -*-
"""apply_v15.py —— [v15] 补齐框**图形**装载器的另两个入口（B/C）的门控。

背景（逐指令 + 源码实证，2026-09-11）：
  官方「框」= 图形 + tilemap 两截。图形那一截有 **三个** 函数，都读同一个
  全局框号 `sTextWindowBaseTileNum (0x03000514)`、都往 `VRAM基址 + 32*框号` 拷
  9 个 tile：
    A `0x08062094` TextWindow_LoadStdFrameGraphics              ← v12 已门控
    B `0x080620C8` TextWindow_LoadStdFrameGraphicsOverridePal   ← v15 补
    C `0x08062100` TextWindow_LoadStdFrameGraphicsOverrideStyle ← v15 补
  v14 把 tilemap 门控成「框号 == 0 ⇒ 擦成 0 号 tile」。若 B/C 在框号 == 0 时
  仍跑，就会把框美术写到 **tile 0..8**，而 v14 的擦除正指向 **tile 0**
  ⇒ 擦除结果仍是框美术 ⇒ 「满池 UI 仍不空」。故必须补齐。

钩点选在**函数体中段的「读框号」处**（不是入口）——那里寄存器压力为零：
  现场 r1 = VRAM 基址（前一条 `adds r1,r0,#0` 已就位）、r3 已死、
  r4(B)/r5(B) 是入参必须保活，跳板一律不碰。续跑 = 把被桩盖掉的
  `ldrh / lsls / adds` 重放完，落到桩之后的指令；跳过 = 直接跳原体 epilogue。

两遍式：第一遍全在内存改完，任一锚点不匹配即整体不写盘。
"""
import io
import os
import sys

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "configs", "POKEMON_RUBY_AXVJ00", "hook")

EDITS = []


def add(rel, old, new, times=1):
    EDITS.append((rel, old, new, times))


# ---------------------------------------------------------------- 1) game_addrs.asm
A_ADDRS = """;
; [v15] 框**图形**装载器的另两个入口（2026-09-11）
;   官方「框」的图形那一截有 3 个函数，**都读同一个全局框号** `0x03000514`
;   并把 9 个 tile 拷到 `VRAM基址 + 32*框号`：
;     A TextWindow_LoadStdFrameGraphics            @0x08062094  ← v12 已门控
;     B TextWindow_LoadStdFrameGraphicsOverridePal @0x080620C8  ← 本次补
;     C TextWindow_LoadStdFrameGraphicsOverrideStyle @0x08062100 ← 本次补
;   框号 == 0 时 B/C 仍会把这 9 个 tile 写到 **tile 0..8**，而 v14 的擦除正把
;   tilemap 指向 **tile 0** ⇒ 擦完还是框美术。故 v15 在两点补同一个门控。
;
;   ⚠ 两点都不在函数入口，而在**函数体中段读框号处**：
;     B @0x080620D4  现场 r1 = VRAM 基址（0x080620D2 已 `adds r1,r0,#0`）
;     C @0x0806210C  现场 r1 = VRAM 基址（0x0806210A 已 `adds r1,r0,#0`）
;   两处 r3 都已死、r4/r5 是入参（跳板不得碰）⇒ 桩/跳板零寄存器压力。
StdFrameLoadPalBase_Load               equ 0x080620D4
StdFrameLoadStyleBase_Load             equ 0x0806210C
"""
add("game_addrs.asm",
    "TextWindow_DrawDialogueFrame           equ 0x0806266C\n",
    "TextWindow_DrawDialogueFrame           equ 0x0806266C\n" + A_ADDRS)

# ---------------------------------------------------------------- 2) hooks_origin.s
S_HOOKS = """
; 框图形装载器 B / C 的「读框号」处 —— 各覆盖 8 字节
;   B: 0x080620D4 (ldr r0,=0x03000514) / D6 (ldrh) / D8 (lsls r0,r0,#5)
;      / DA (adds r1,r1,r0)                    ⇒ 续跑 0x080620DC
;   C: 0x0806210C (ldr r0,=0x03000514) / 0E (ldrh) / 10 (lsls r0,r0,#5)
;      / 12 (adds r1,r1,r0)                    ⇒ 续跑 0x08062114
;   桩型 = **8B「不碰栈」纯跳转**（ldr r3 / bx r3 / .pool），与 v14 两处同型：
;   两点都在函数体中段，原体自己的 prologue 已压好 callee-saved、epilogue 会还原。
.org StdFrameLoadPalBase_Load
    ldr  r3, =(V15LoadPal_Hook | 1)
    bx   r3
.pool

.org StdFrameLoadStyleBase_Load
    ldr  r3, =(V15LoadStyle_Hook | 1)
    bx   r3
.pool
"""
add("src/text/hooks_origin.s",
    """.org TextWindow_DrawDialogueFrame
    ldr  r3, =(V14DlgFrame_Hook | 1)
    bx   r3
.pool
""",
    """.org TextWindow_DrawDialogueFrame
    ldr  r3, =(V14DlgFrame_Hook | 1)
    bx   r3
.pool
""" + S_HOOKS)

# ---------------------------------------------------------------- 3) entry.s
E_HOOKS = """
@ =============================================================================
@ [v15] 框**图形**装载器的另两个入口 —— 与 ⑦ 同一个门控（2026-09-11）
@ -----------------------------------------------------------------------------
@ 源码（tools/pokeruby/src/text_window.c:108/116/124）三个函数体只差最后两个
@ helper 的入参，**图形目的地址完全相同**：
@     tileData = win->template->tileData + TILE_SIZE_4BPP * sTextWindowBaseTileNum
@ 所以「框号 == 0 ⇒ 不装载」对三者必须一致，否则框号 0 时框美术落到 tile 0..8，
@ 正好被 v14 的「擦成 0 号 tile」照出来。
@
@ 🔴 钩点不在入口，而在**读框号处**（B @0x080620D4 / C @0x0806210C）：
@    现场 r1 已经 = VRAM 基址（前一条 `adds r1,r0,#0`），我们只需重放
@      ldr r0,=0x03000514 / ldrh r0,[r0] / lsls r0,r0,#5 / adds r1,r1,r0
@    落到桩尾之后继续；r3 在两处都已死（B 的 0x080620DC 会 ldr r4、C 的
@    0x08062114 会 adds r0,r4,#0）⇒ 可作跳转寄存器。
@    跳过路径 = 直接跳原体 epilogue：
@      B → 0x080620F0（pop {r4,r5} / pop {r0} / bx r0）
@      C → 0x08062122（pop {r4}    / pop {r0} / bx r0）
@ 桩没碰栈、跳过路径也没碰栈 ⇒ 栈完全平衡，`bx r3` 直达前者调用者。
@ =============================================================================
    .global V15LoadPal_Hook
    .thumb_func
    .type V15LoadPal_Hook, %function
V15LoadPal_Hook:
    ldr     r0, =0x03000514            @ 重放 0x080620D4 的字面量槽
    ldrh    r0, [r0]                   @ 重放 0x080620D6
    cmp     r0, #0                     @ 0 = 池子没发出号 ⇒ 不装载
    beq     LoadPalGfx_Skip
    lsls    r0, r0, #5                 @ 重放 0x080620D8（tile → 字节）
    adds    r1, r1, r0                 @ 重放 0x080620DA
    ldr     r3, =0x080620DD            @ 续跑点 0x080620DC（ldr r4,=…）—— |1
    bx      r3
LoadPalGfx_Skip:
    ldr     r3, =0x080620F1            @ B 的 epilogue（0x080620F0 pop {r4,r5}）
    bx      r3
    .size V15LoadPal_Hook, .-V15LoadPal_Hook
    .pool

    .global V15LoadStyle_Hook
    .thumb_func
    .type V15LoadStyle_Hook, %function
V15LoadStyle_Hook:
    ldr     r0, =0x03000514            @ 重放 0x0806210C 的字面量槽
    ldrh    r0, [r0]                   @ 重放 0x0806210E
    cmp     r0, #0                     @ 0 = 池子没发出号 ⇒ 不装载
    beq     LoadStyleGfx_Skip
    lsls    r0, r0, #5                 @ 重放 0x08062110
    adds    r1, r1, r0                 @ 重放 0x08062112
    ldr     r3, =0x08062115            @ 续跑点 0x08062114（adds r0,r4,#0）—— |1
    bx      r3
LoadStyleGfx_Skip:
    ldr     r3, =0x08062123            @ C 的 epilogue（0x08062122 pop {r4}）
    bx      r3
    .size V15LoadStyle_Hook, .-V15LoadStyle_Hook
    .pool

.end
"""
add("src/text/entry.s",
    """    .size V14DlgFrame_Hook, .-V14DlgFrame_Hook
    .pool

.end
""",
    """    .size V14DlgFrame_Hook, .-V14DlgFrame_Hook
    .pool
""" + E_HOOKS)

# ---------------------------------------------------------------- 4) 两个构建脚本
add("build_sh_equiv.sh",
    "           V14StdFrame_Hook V14DlgFrame_Hook; do",
    "           V14StdFrame_Hook V14DlgFrame_Hook \\\n"
    "           V15LoadPal_Hook V15LoadStyle_Hook; do")

add("build.bat",
    "V14StdFrame_Hook V14DlgFrame_Hook) do (",
    "V14StdFrame_Hook V14DlgFrame_Hook V15LoadPal_Hook V15LoadStyle_Hook) do (")


def read(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s, newline):
    data = s.replace("\r\n", "\n").replace("\n", newline)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(data)


problems = []
plan = []
for rel, old, new, times in EDITS:
    p = os.path.join(HOOK, rel)
    if not os.path.exists(p):
        problems.append("%s: 文件不存在" % rel)
        continue
    raw = read(p)
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    n = s.count(old)
    if n != times:
        problems.append("%s: 锚点命中 %d 次，期望 %d 次" % (rel, n, times))
        continue
    plan.append((p, s.replace(old, new, times), "\r\n" if crlf else "\n", rel))

if problems:
    print("!! 有 %d 处锚点问题，**未写盘**：" % len(problems))
    for x in problems:
        print("   " + x)
    sys.exit(1)

for p, s, nl, rel in plan:
    before = len(read(p))
    write(p, s, nl)
    print("  OK  %-28s %d → %d B  (%s)" % (rel, before, len(read(p)), "CRLF" if nl == "\r\n" else "LF"))
print("apply_v15 完成：%d 个文件" % len(plan))
