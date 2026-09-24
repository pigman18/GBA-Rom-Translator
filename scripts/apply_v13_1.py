# -*- coding: utf-8 -*-
"""v13.1：补写 gTplSlot —— 0x080028BC（菜单窗口图形装载）入口钩。

病灶：v13 的 ⑤ 替换实现 `v10_set_frame_base_C` 用 `0x03000328`(gTplSlot) 取本窗模板
（`v8_alloc_core` 要靠 tpl 算 charBase / tileData 做三层占用校验）。而官方**有两条**
窗口装载路径，只有 ① `0x08002950` 写这个槽；`0x080028BC` 是它的姊妹路径
（同样 `strh r3,[r2,#0x16]` 写 win[0x16]、同样按 textMode+fontNum 分派装载
0x08002AF4/2B2C/2B60/2B9C），却不写 gTplSlot。

`0x080028BC` 的调用点全盘只有 2 个 —— `0x0806F090` / `0x0806F106`，都在菜单窗口
初始化里。而「继续游戏」是游戏启动后的第一个 UI ⇒ ⑤ 拿到空 tpl ⇒
`v8_alloc_core` 的 `if (!tpl) return 0` 命中 ⇒ 框号 0 ⇒ ⑦⑧ 的 hook 读到
0x03000514 == 0 ⇒ 不装载 ⇒ 菜单 UI 整条空白。
（v12 的纯计数器 `v10_frame_alloc` 不看 tpl，所以这个坑到 v13 才暴露。）

本脚本只做一件事：把两条路径归一 —— 在 0x080028BC 入口把 win[0] (tpl) 写回 gTplSlot。
"""
import pathlib, sys

HK = pathlib.Path(r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook")

def patch(rel, subs):
    p = HK / rel
    raw = p.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    t = raw.decode("utf-8").replace("\r\n", "\n")
    for i, (old, new, cnt) in enumerate(subs, 1):
        got = t.count(old)
        if got != cnt:
            print("!!! MISS %s sub#%d: want %d got %d" % (rel, i, cnt, got))
            print("---- old ----")
            print(old[:300])
            sys.exit(1)
        t = t.replace(old, new)
    out = t.replace("\n", nl).encode("utf-8")
    p.write_bytes(out)
    print("OK  %-28s %6d B -> %6d B  (%s)" % (rel, len(raw), len(out), "CRLF" if nl == "\r\n" else "LF"))

# ---------------------------------------------------------------- A. game_addrs.asm
ADDR_BLOCK = r"""
; 0x080028BC —— 菜单窗口**图形**装载（① 的姊妹路径；2026-09-11 逐指令定案）。
; 原体：push {lr} / adds r2,r0 / lsls r1 / lsrs r3 / strh r3,[r2,#0x16]
;       / ldr r0,[r2] / 按 tpl->textMode + tpl->fontNum 分派：
;         tm3  → bl 0x08002BD0(win, off)
;         否则查 fontNum 跳转表 0x08002900（7 项，实测）：
;           fn0,fn3 → 0x08002AF4 | fn1,fn2 → 0x08002B2C
;           fn4,fn5 → 0x08002B60 | fn6     → 0x08002B9C
;       四个装载器各只有 1 个调用点（都在本函数内），每个往
;       `win[0xc] + offset*32` 写 512 tile 图形（循环 256 次、每次 +64B）。
; 🔴 它**不写** 0x03000328(gTplSlot) / 0x0300032C(gTplBase) / 0x0300032E(gAtlasCur)
;    —— 全盘只有 ① `0x08002950` 写这三槽（实测 gTplSlot 仅 3 处引用，全在 ①/③ 内）。
; 🔴 调用点**全盘只有 2 个**：0x0806F090 / 0x0806F106（菜单窗口初始化）。
;    ⇒ 「继续游戏」菜单走这条路，而我们的 ⑤ 用 gTplSlot 取模板 ⇒ 拿到 0 或上一个
;      窗口的残值 ⇒ v8_alloc_ui 返 0 ⇒ 框整条消失（v13 回归）。
;    ⇒ v13.1 在本函数入口补写 gTplSlot，让两条装载路径归一（entry.s:V13WinGfx_Hook）。
WinGfxLoad                             equ 0x080028BC
"""

patch("game_addrs.asm", [(
    "TextWindow_LoadDlgFrameGraphics        equ 0x08062684",
    "TextWindow_LoadDlgFrameGraphics        equ 0x08062684\n" + ADDR_BLOCK,
    1,
)])

# ---------------------------------------------------------------- B. hooks_origin.s
STUB = r"""
; [v13.1] WinGfxLoad @0x080028BC —— 菜单窗口图形装载；补写 gTplSlot
; ---------------------------------------------------------------
; 为什么必须接这里：⑤ 的替换实现 `v10_set_frame_base_C` 要用 0x03000328(gTplSlot)
;   当模板指针（v8_alloc_core 靠 tpl 算 charBase / tileData 做三层占用校验）。
;   而 gTplSlot **全盘只有 ① `0x08002950` 写**；本函数是 ① 的姊妹路径
;   （同样 `strh r3,[r2,#0x16]` 写 win[0x16]、同样按 tm+fontNum 分派装载），
;   却**不写 gTplSlot**。它的调用点全盘只有 2 个，都在菜单初始化
;   （0x0806F090 / 0x0806F106）⇒ 「继续游戏」菜单的 ⑤ 拿到空 tpl
;   ⇒ `v8_alloc_core` 第一步 `if (!tpl) return 0` 命中 ⇒ 框号 = 0
;   ⇒ ⑦⑧ 的 hook 读到 0x03000514 == 0 ⇒ 不装载 ⇒ 菜单 UI 空白。
;
; 桩型：12B「尾跳」。原体**只 push {lr}**（epilogue `pop {r1}; bx r1`）⇒ 桩也只能
;   压 lr；跳转寄存器用 r3（caller-saved；原体下次用 r3 在 0x0800291E，跳板会把
;   `lsrs r3, r1, #0x10` 重放回去）。
;   覆盖 0x080028BC..0x080028C7（含 .pool 对齐填充），续跑点 0x080028C8。
.org WinGfxLoad
    push {lr}
    ldr  r3, =(V13WinGfx_Hook | 1)
    bx   r3
.pool
"""

patch("src/text/hooks_origin.s", [(
    ".org TextWindow_LoadDlgFrameGraphics\n"
    "    push {lr}\n"
    "    ldr  r3, =(V12DlgFrame_Hook | 1)\n"
    "    bx   r3\n"
    ".pool",
    ".org TextWindow_LoadDlgFrameGraphics\n"
    "    push {lr}\n"
    "    ldr  r3, =(V12DlgFrame_Hook | 1)\n"
    "    bx   r3\n"
    ".pool\n" + STUB,
    1,
)])

# ---------------------------------------------------------------- C. entry.s
TRAMP = r"""
@ =============================================================================
@ [v13.1] 菜单窗口图形装载 0x080028BC —— 补写 gTplSlot（2026-09-11）
@ -----------------------------------------------------------------------------
@ 为什么：⑤ 的 C 实现（win_alloc.c:v10_set_frame_base_C）要用 0x03000328(gTplSlot)
@   取本窗模板，`v8_alloc_core` 才能算 charBase / tileData 做三层占用校验。
@   而该槽**全盘只有 ① `0x08002950` 写**；0x080028BC 是 ① 的姊妹路径
@   （同样 `strh r3,[r2,#0x16]` 写 win[0x16]、同样按 tm+fontNum 分派装载），
@   却不写 gTplSlot。它的 2 个调用点全在菜单初始化
@   （0x0806F090 / 0x0806F106）⇒ 「继续游戏」菜单的 ⑤ 拿到空 tpl
@   ⇒ `v8_alloc_core` 的 `if (!tpl) return 0` 命中 ⇒ 框号 0 ⇒ ⑦⑧ 读 0
@   ⇒ 不装载 ⇒ 菜单 UI 空白。
@ 桩（hooks_origin.s）是 12B「尾跳」：push {lr} / ldr r3 / bx r3 / .pool，
@   覆盖 0x080028BC..0x080028C7；本跳板重放被盖掉的
@   0x080028BE..0x080028C6 五条，再回 0x080028C8 续跑。
@
@ 🔴 栈账（原体只 push {lr}、只 pop {r1} ⇒ 必须严格对齐）：
@   调用者 bl         SP = S-4 : [S-4] = 返回地址(兼作 LR)
@   桩 push {lr}      SP = S-8 : [S-8] = 返回地址
@   桩 bx r3          SP = S-8（LR 寄存器未动 ⇒ 与栈上那份同值）
@   跳板 push{r0..r3} SP = S-24
@   跳板 bl C         SP = S-24（LR 被覆盖，但栈上有副本）
@   跳板 pop{r0..r3}  SP = S-8
@   跳板 bx 0x028C8   原体跑完 → pop {r1} 弹 [S-8] → SP = S-4 … ⚠ 见下
@
@ ⚠ 修正上面最后一格：原体 epilogue 是 `pop {r1}; bx r1` —— 它弹走**栈顶**那份，
@   而栈顶正是桩压的返回地址 ⇒ SP 回到 S-4 ⇒ bx 回调用者，调用者的 SP 也正确。
@   （`bl` 进 0x080028BC 时调用者并没有额外压栈；S-4 就是调用前的 SP。）
@ ✅ 跳转寄存器用 r1：重放完它已是死值（原体下次用 r1 是在 0x080028EA 的
@   `ldrb r1,[r0,#8]`，会重设）。绝不能用 r3（原体 0x0800291E 要用它当 offset）。
@ =============================================================================
    .global V13WinGfx_Hook
    .thumb_func
    .type V13WinGfx_Hook, %function
    .extern v13_set_tpl_C
V13WinGfx_Hook:
    push    {r0, r1, r2, r3}           @ 保参（C 会砸 r0-r3）
    bl      v13_set_tpl_C              @ r0 = win ⇒ 写 0x03000328 = win->tpl
    pop     {r0, r1, r2, r3}
    adds    r2, r0, #0                 @ 重放 0x080028BE
    lsls    r1, r1, #0x10              @ 重放 0x080028C0
    lsrs    r3, r1, #0x10              @ 重放 0x080028C2
    strh    r3, [r2, #0x16]            @ 重放 0x080028C4
    ldr     r0, [r2]                   @ 重放 0x080028C6
    ldr     r1, =0x080028C9            @ 续跑点（ldrb r0,[r0,#9]）—— |1 保 Thumb
    bx      r1
    .size V13WinGfx_Hook, .-V13WinGfx_Hook
"""

patch("src/text/entry.s", [(
    "    .size V12DlgFrame_Hook, .-V12DlgFrame_Hook\n    .pool\n\n.end",
    "    .size V12DlgFrame_Hook, .-V12DlgFrame_Hook\n    .pool\n" + TRAMP + "    .pool\n\n.end",
    1,
)])

# ---------------------------------------------------------------- D. win_alloc.h
DECL = r"""
/* v13.1（2026-09-11）：补写 gTplSlot —— 由 `0x080028BC`（菜单窗口图形装载、
 * ① 的姊妹路径）入口钩调用。
 *
 * 官方的两条窗口装载路径里**只有 ① `0x08002950` 写 `0x03000328`**；
 * `0x080028BC` 同样写 `win[0x16]`、同样按 textMode+fontNum 分派装载
 * （0x08002AF4/2B2C/2B60/2B9C），却不写 gTplSlot。它的调用点全盘仅 2 个
 * （0x0806F090 / 0x0806F106，都在菜单初始化）。
 *
 * ⇒ ⑤ 的替换实现要用 gTplSlot 取模板（`v8_alloc_core` 靠它算 charBase /
 *   tileData），这条路径上拿到的是空值 ⇒ 返 0 ⇒ 框整条不画。
 *   本函数拿 win 换 tpl 写回同一个槽，让两条路径归一。 */
void v13_set_tpl_C(uint8_t *win);
"""

patch("include/win_alloc.h", [(
    "uint16_t v10_set_frame_base_C(uint16_t official_base);\n\n#endif /* WIN_ALLOC_H */",
    "uint16_t v10_set_frame_base_C(uint16_t official_base);\n" + DECL + "\n#endif /* WIN_ALLOC_H */",
    1,
)])

# ---------------------------------------------------------------- E. win_alloc.c
IMPL = r"""

/* ============================================================================
 * v13.1（2026-09-11）：补写 gTplSlot —— 0x080028BC「菜单窗口图形装载」入口钩。
 *
 * 病灶：`v10_set_frame_base_C` 用 `0x03000328`(gTplSlot) 取本窗模板，好让
 *   `v8_alloc_core` 算出 charBase / tileData 做三层占用校验。而官方**有两条**
 *   窗口装载路径，只有 ① `0x08002950` 写这个槽；`0x080028BC` 是它的姊妹
 *   （同样 `strh r3,[r2,#0x16]` 写 win[0x16]、同样按 textMode+fontNum 分派
 *   装载 0x08002AF4/2B2C/2B60/2B9C），却不写。
 *
 *   `0x080028BC` 的调用点全盘只有 2 个 —— `0x0806F090` / `0x0806F106`，
 *   都在菜单窗口初始化里。而「继续游戏」是游戏启动后的第一个 UI
 *   ⇒ ⑤ 拿到的 gTplSlot 是 0（或更早某个窗口的残值）
 *   ⇒ `v8_alloc_core` 的 `if (!tpl) return 0` 命中 ⇒ 框号 = 0
 *   ⇒ ⑦⑧ 的 hook 读到 `0x03000514 == 0` ⇒ 不装载 ⇒ **菜单 UI 整条空白**。
 *   （v12 的纯计数器 `v10_frame_alloc` 不看 tpl，所以这个坑到 v13 才暴露。）
 *
 * 修法 = 把两条路径归一：在本函数入口把 win[0] (tpl) 写回 gTplSlot。
 *   不改任何官方语义 —— 该槽本来就是「当前窗口模板」的权威副本，
 *   这里只是补上官方漏掉的另一半。
 * ==========================================================================*/
void v13_set_tpl_C(uint8_t *win)
{
    uint8_t *tpl;

    if (!win)
        return;
    tpl = *(uint8_t *volatile *)win;            /* win[0] = 模板指针（首字段） */
    if (!tpl)
        return;
    *(uint8_t *volatile *)0x03000328u = tpl;    /* gTplSlot */
}
"""

patch("src/text/win_alloc.c", [(
    "    return (uint16_t)(c + 9u);\n}",
    "    return (uint16_t)(c + 9u);\n}" + IMPL,
    1,
)])

# ---------------------------------------------------------------- F/G. build 符号清单
patch("build_sh_equiv.sh", [(
    "V12StdFrame_Hook V12DlgFrame_Hook; do",
    "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook; do",
    1,
)])

patch("build.bat", [(
    "V12StdFrame_Hook V12DlgFrame_Hook) do (",
    "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook) do (",
    1,
)])

print("\nALL PATCHES APPLIED")
