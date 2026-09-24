# -*- coding: utf-8 -*-
"""v13.2：把「本窗模板」的来源从 gTplSlot 扩到「最近初始化的窗口」。

v13.1 钩了 0x080028BC（菜单图形装载）补写 gTplSlot，但漏了半条链：
    0x0806F074 链: InitWindow → 0x080028BC → ⑤ → ⑦ → ⑥      ✅ v13.1 有效
    0x0806F0D0 链: InitWindow → ⑤ → ⑦ → ⑥ → 0x080028BC      ❌ ⑤ 早于 0x080028BC
「继续游戏」走的很可能就是 0x0806F0D0（重新初始化）⇒ 仍然返 0 ⇒ 框空白。

两条链的唯一共同前置是 InitWindow(0x08002C28)。但入口时 win[0] 还没写
（0x08002C42 `str r0,[r4]` 才写）。所以钩 0x08002C44 —— 它之后 r4=win、r0=tpl。

为什么跳转寄存器可以用 r5：原体 0x08002C34..3C 用 r2/r3/r5/r6 搬模板表，
但到 0x08002C44 之后**只有 r0/r1/r4 还在用**；r5 是 callee-saved 且原体
push 过它 ⇒ epilogue 的 `pop {r4,r5,r6}` 会恢复。
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
            print("---- old ----"); print(old[:300]); sys.exit(1)
        t = t.replace(old, new)
    out = t.replace("\n", nl).encode("utf-8")
    p.write_bytes(out)
    print("OK  %-28s %6d B -> %6d B  (%s)" % (rel, len(raw), len(out), "CRLF" if nl == "\r\n" else "LF"))

# ---------------------------------------------------------------- A. game.h
GAMEH = r"""
/* --- 手工追加（非生成区）：v13.2 最近初始化的窗口指针（2026-09-11）--------
 * 用途：⑤ 的替换实现要拿「本窗模板」才能让 `v8_alloc_core` 算 charBase /
 *   tileData。官方 gTplSlot(0x03000328) **只有 ① `0x08002950` 填**，而菜单的
 *   另一条初始化链（0x0806F0D0）里 ⑤ 早于 0x080028BC ⇒ 那一步拿不到模板。
 *   窗口自己知道模板（InitWindow 在 0x08002C42 写 win[0] = tpl）⇒ 记 win 指针即可。
 * 落 0x0203FFB0 —— ours 位图（0x0203FF70..AF）之后、游戏数据（0xFFD0）之前的空档；
 *   ADDR_CHS_PHASE(0x0203FF90) 全仓无引用点，不冲突。 */
#define ADDR_V13_LAST_WIN                  0x0203FFB0u
"""
patch("include/game.h", [(
    "#define ADDR_V8Q_TPL                       0x0203FF58u\n",
    "#define ADDR_V8Q_TPL                       0x0203FF58u\n" + GAMEH,
    1,
)])

# ---------------------------------------------------------------- B. game_addrs.asm
ADDRS = r"""
; 0x08002C28 InitWindow(win, templateId)：从模板表 0x081B3484 拷 9 字进 win，
;   再 `bl 0x08004228(templateId)` 取模板指针写进 win[0]（= 0x08002C42 `str r0,[r4]`）。
;   0x08002C44 = 那之后的第一条（`ldrb r1,[r0,#9]`）——
;   v13.2 在此挂桩：记下 win 指针（r4）供 ⑤ 取本窗模板，见 entry.s:V13NoteWin_Hook。
;   全盘 `bl InitWindow` 有 30 处，是「创建窗口」的唯一通用入口。
InitWindow                             equ 0x08002C28
InitWindow_AfterTpl                    equ 0x08002C44
"""
patch("game_addrs.asm", [(
    "WinGfxLoad                             equ 0x080028BC\n",
    "WinGfxLoad                             equ 0x080028BC\n" + ADDRS,
    1,
)])

# ---------------------------------------------------------------- C. hooks_origin.s
STUB = r"""
; [v13.2] InitWindow @0x08002C28 —— 记「最近初始化的窗口」（钩点在函数中部 0x08002C44）
; ---------------------------------------------------------------
; 为什么钩中部而不是入口：入口时 win[0]（模板指针）还没写 —— 它在 0x08002C42
;   的 `str r0,[r4]` 才落地。0x08002C44 是那之后的第一条，此时 r4 = win、r0 = tpl。
; 为什么必须钩这里：⑤ 的替换实现要用本窗模板（v8_alloc_core 靠它算 charBase /
;   tileData）。官方 gTplSlot **只有 ① 填**；菜单的另一条初始化链
;   0x0806F0D0 里 ⑤（0x0806F0EA）早于 0x080028BC（0x0806F106）
;   ⇒ 那一步的 ⑤ 拿到空/旧模板 ⇒ 返 0 ⇒ 框整条不画。
; 栈：本桩**不碰栈**（只 ldr/bx），原体 0x08002C28 push 的 {r4,r5,r6,lr}
;   由原体 epilogue `pop {r4,r5,r6}` + `pop {r0}` 照常收。
; 跳转寄存器 r5：原体从 0x08002C4C 起只用 r0/r1/r4（r2/r3/r5/r6 的模板搬运已结束），
;   且 r5 是 callee-saved、原体 push 过 ⇒ epilogue 会恢复它。
; 覆盖 0x08002C44..0x08002C4B（ldr r5 / bx r5 / .pool 对齐），续跑点 0x08002C4C。
.org InitWindow_AfterTpl
    ldr  r5, =(V13NoteWin_Hook | 1)
    bx   r5
.pool
"""
patch("src/text/hooks_origin.s", [(
    ".org WinGfxLoad\n"
    "    push {lr}\n"
    "    ldr  r3, =(V13WinGfx_Hook | 1)\n"
    "    bx   r3\n"
    ".pool",
    ".org WinGfxLoad\n"
    "    push {lr}\n"
    "    ldr  r3, =(V13WinGfx_Hook | 1)\n"
    "    bx   r3\n"
    ".pool\n" + STUB,
    1,
)])

# ---------------------------------------------------------------- D. entry.s
TRAMP = r"""
@ =============================================================================
@ [v13.2] InitWindow 0x08002C44 —— 记「最近初始化的窗口」+ 补 gTplSlot（2026-09-11）
@ -----------------------------------------------------------------------------
@ 为什么：⑤ 的 C 实现要用本窗模板（`v8_alloc_core` 靠它算 charBase / tileData）。
@   官方 gTplSlot(0x03000328) **只有 ① 填**；菜单的另一条初始化链
@   0x0806F0D0 里 ⑤（0x0806F0EA）**早于** 0x080028BC（0x0806F106）
@   ⇒ 那一步的 ⑤ 拿到空/旧模板 ⇒ 返 0 ⇒ 框整条不画（用户实测「继续游戏菜单 UI 空白」）。
@   v13.1 钩 0x080028BC 只覆盖了另一条链（0x0806F074: 0x080028BC 在 ⑤ 之前）。
@   窗口自己知道模板：InitWindow 在 0x08002C42 写 `win[0] = tpl`
@   ⇒ 在它之后的第一条（0x08002C44）记下 win 指针，⑤ 时读 win[0]。
@
@ 钩点现场：r4 = win，r0 = tpl；栈上是原体 0x08002C28 push 的 {r4,r5,r6,lr}。
@ 桩（hooks_origin.s）是「原地 ldr r5 / bx r5 / .pool」，覆盖 0x08002C44..0x08002C4B；
@   本跳板重放被盖掉的 0x08002C44..0x08002C4B 四条（ldrb/strb ×2），再回
@   0x08002C4C（`ldrb r1,[r0,#5]`）续跑。
@ 🔴 本跳板**不碰栈**（push/pop 成对）⇒ 原体 epilogue 照常。
@ 🔴 跳转寄存器用 r5：原体从 0x08002C4C 起只用 r0/r1/r4（r2/r3/r5/r6 的模板搬运
@   已结束），且 r5 是 callee-saved、原体 push 过 ⇒ epilogue 的 pop{r4,r5,r6} 会恢复。
@   绝不能用 r2/r3（0x08002C34..3C 的 stm/ldm 还要用）。
@ =============================================================================
    .global V13NoteWin_Hook
    .thumb_func
    .type V13NoteWin_Hook, %function
    .extern v13_note_win_C
V13NoteWin_Hook:
    push    {r0, r1, r2, r3}           @ 保参（C 会砸 r0-r3）
    adds    r0, r4, #0                 @ r0 = win
    bl      v13_note_win_C             @ 记 win 指针 + 写 gTplSlot
    pop     {r0, r1, r2, r3}           @ 恢复 r0 = tpl
    ldrb    r1, [r0, #9]               @ 重放 0x08002C44
    strb    r1, [r4, #0xa]             @ 重放 0x08002C46
    ldrb    r1, [r0, #8]               @ 重放 0x08002C48
    strb    r1, [r4, #0xb]             @ 重放 0x08002C4A
    ldr     r5, =0x08002C4D            @ 续跑点（ldrb r1,[r0,#5]）—— |1 保 Thumb
    bx      r5
    .size V13NoteWin_Hook, .-V13NoteWin_Hook
"""
patch("src/text/entry.s", [(
    "    .size V13WinGfx_Hook, .-V13WinGfx_Hook\n    .pool\n\n.end",
    "    .size V13WinGfx_Hook, .-V13WinGfx_Hook\n    .pool\n" + TRAMP + "    .pool\n\n.end",
    1,
)])

# ---------------------------------------------------------------- E. win_alloc.h
DECL = r"""
/* v13.2（2026-09-11）：记「最近初始化的窗口」—— 由 `InitWindow` 的中部钩
 * `0x08002C44`（`win[0] = tpl` 之后第一条）调用。
 *
 * 官方 gTplSlot(0x03000328) **只有 ① `0x08002950` 填**，而窗口模板的权威副本
 * 是 `win[0]`（InitWindow 在 0x08002C42 写入）。菜单的另一条初始化链
 * （0x0806F0D0）里 ⑤ 早于 0x080028BC ⇒ 那一步拿不到模板。
 * 本函数同时把 win 指针记到 `ADDR_V13_LAST_WIN` 并补写 gTplSlot。 */
void v13_note_win_C(uint8_t *win);
"""
patch("include/win_alloc.h", [(
    "void v13_set_tpl_C(uint8_t *win);\n",
    "void v13_set_tpl_C(uint8_t *win);\n" + DECL,
    1,
)])

# ---------------------------------------------------------------- F. win_alloc.c
IMPL = r"""

/* ============================================================================
 * v13.2（2026-09-11）：记「最近初始化的窗口」—— InitWindow 中部钩 0x08002C44。
 *
 * 病灶（v13.1 漏掉的半条链）：
 *   官方两条菜单窗口初始化链的顺序**相反** ——
 *     0x0806F074: InitWindow → 0x080028BC(0x06F090) → ⑤(0x06F09A) → ⑦ → ⑥
 *     0x0806F0D0: InitWindow → ⑤(0x06F0EA) → ⑦ → ⑥ → 0x080028BC(0x06F106)
 *   前者 0x080028BC 在 ⑤ 之前（v13.1 已覆盖）；后者**在 ⑤ 之后**
 *   ⇒ ⑤ 拿到的 gTplSlot 是空的或上一个窗口的 ⇒ `v8_alloc_core` 返 0
 *   ⇒ 框号 0 ⇒ ⑦⑧ 读到 0x03000514 == 0 ⇒ 不装载 ⇒ 菜单 UI 空白。
 *   而「继续游戏」走的很可能就是后者（重新初始化）。
 *
 * 修法：窗口自己知道模板 —— InitWindow 在 0x08002C42 写 `win[0] = tpl`。
 *   在它之后的第一条（0x08002C44）把 win 记下来；⑤ 时读 `win[0]`。
 *   两条链都经过 InitWindow ⇒ 全覆盖。（gTplSlot 仍同步更新，作为次要副本。）
 * ==========================================================================*/
void v13_note_win_C(uint8_t *win)
{
    uint8_t *tpl;

    if (!win)
        return;
    *(uint8_t *volatile *)(uintptr_t)ADDR_V13_LAST_WIN = win;
    tpl = *(uint8_t *volatile *)win;            /* InitWindow 刚写的 win[0] */
    if (tpl)
        *(uint8_t *volatile *)0x03000328u = tpl;   /* gTplSlot（次要副本） */
}

/* 本窗模板：优先「最近初始化的窗口」自己的 win[0]（唯一能覆盖官方两条装载
 * 路径的来源）；gTplSlot 作兜底（它只被 ① 和 0x080028BC 填）。
 * ⑤ 恒在窗口初始化之后被调 ⇒ 「最近的那个窗口」就是本窗。 */
static uint8_t *v13_cur_tpl(void)
{
    uint8_t *win = *(uint8_t *volatile *)(uintptr_t)ADDR_V13_LAST_WIN;
    uint8_t *tpl;

    if (win)
    {
        tpl = *(uint8_t *volatile *)win;
        if (tpl)
            return tpl;
    }
    return *(uint8_t *volatile *)0x03000328u;
}
"""
# IMPL 必须插在 v10_set_frame_base_C **之前**（v13_cur_tpl 是 static，需先定义）
patch("src/text/win_alloc.c", [(
    "uint16_t v10_set_frame_base_C(uint16_t official_base)",
    IMPL.strip() + "\n\nuint16_t v10_set_frame_base_C(uint16_t official_base)",
    1,
)])

# gTplSlot 取模板 → 改走 v13_cur_tpl()
patch("src/text/win_alloc.c", [(
    "    uint8_t *tpl = *(uint8_t *volatile *)0x03000328u;   /* ① 写的本窗模板 */",
    "    uint8_t *tpl = v13_cur_tpl();   /* v13.2：最近初始化的窗口的 win[0]（gTplSlot 兜底）*/",
    1,
)])

# ---------------------------------------------------------------- G. build 符号清单
patch("build_sh_equiv.sh", [(
    "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook; do",
    "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook V13NoteWin_Hook; do",
    1,
)])
patch("build.bat", [(
    "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook) do (",
    "V12StdFrame_Hook V12DlgFrame_Hook V13WinGfx_Hook V13NoteWin_Hook) do (",
    1,
)])

print("\nALL PATCHES APPLIED (v13.2)")
