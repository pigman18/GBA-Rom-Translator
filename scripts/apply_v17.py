#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v17 补丁（2026-09-11）：两件事

① **删掉 v16 的第二关**（`v8_frame_room`）—— 它要求「23 个连续可用砖」，
   在官方图形碎片化的窗口里会误判「给不出」⇒ 把本来正常的菜单框也擦掉
   （用户实测：继续游戏菜单 UI 直接没了）。判据回退为 v14 的「槽 == 0 ⇒ 擦」，
   也就是 ⑤ 自己的判决。
   同时删掉 `v8_frame_room` 本体与声明（用户纪律：「先删我上一轮的产物」）。

② **补上真正漏掉的消费者：窗口背景砖号 `GetBlankTileNum` @0x080041BC**。
   官方「窗口」在屏上可见的部分有两类：
     ① 框（图形 tilemap）—— v12/v14/v15 已接；
     ② **窗口内容区的底色** —— 由 `GetBlankTileNum` 给的「空白砖」填出来
        （`Text_ClearWindow` 清整窗 / `Text_BlankWindowRect` 填矩形 /
          `DoScroll_TextMode0` 滚动补行；全盘只有这 3 个调用点，反汇编实证）。
   ② 的号是**硬编码官号**（`win[0x16]`，fontNum∈{1,2,4,5} 再 +212），从不经过池子
   ⇒ 池子满后：文字领不到号（不画），② 照样把窗口填成官号砖
   ⇒ 「文字空、UI 不空」。
   新语义：**池子连一个砖都给不出 ⇒ 返回 0** ⇒ 3 个调用点填
   `paletteNum<<12 | 0` = 0 号砖 = 官方自己的 erase 约定 ⇒ 窗口底色也一起空白。

改动文件（7 个）：
  hook/game_addrs.asm                  + GetBlankTileNum equ
  hook/src/text/hooks_origin.s         + GetBlankTileNum 入口桩
  hook/src/text/entry.s                - v16 两处关卡 / + V17BlankTile_Hook
  hook/include/tile_alloc.h            v8_frame_room → v17_blank_tile_C
  hook/src/text/tile_alloc.c           v8_frame_room 本体 → v17_blank_tile_C 本体
  hook/build_sh_equiv.sh               + 符号 V17BlankTile_Hook
  hook/build.bat                       + 符号 V17BlankTile_Hook

两遍式：第一遍全在内存改完并收集问题；有任一锚点对不上就整体不写盘。
"""
import io
import os
import sys

HOOK = r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook"

FILES = {
    "addrs": os.path.join(HOOK, "game_addrs.asm"),
    "stubs": os.path.join(HOOK, "src", "text", "hooks_origin.s"),
    "entry": os.path.join(HOOK, "src", "text", "entry.s"),
    "tah":   os.path.join(HOOK, "include", "tile_alloc.h"),
    "tac":   os.path.join(HOOK, "src", "text", "tile_alloc.c"),
    "sh":    os.path.join(HOOK, "build_sh_equiv.sh"),
    "bat":   os.path.join(HOOK, "build.bat"),
}


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    crlf = raw.count(b"\r\n")
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return text, ("\r\n" if crlf else "\n")


def save(path, text, nl):
    data = text.replace("\n", nl).encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def rep(text, old, new, tag, problems):
    n = text.count(old)
    if n != 1:
        problems.append("%s: 锚点命中 %d 次（应为 1）" % (tag, n))
        return text
    return text.replace(old, new, 1)


def cut(text, start_marker, end_marker, new, tag, problems):
    """删除 [start_marker .. end_marker) 整段（end_marker 保留）。"""
    a = text.find(start_marker)
    if a < 0:
        problems.append("%s: 找不到起点锚" % tag)
        return text
    b = text.find(end_marker, a)
    if b < 0:
        problems.append("%s: 找不到终点锚" % tag)
        return text
    if text.count(start_marker) != 1 or text.count(end_marker) < 1:
        problems.append("%s: 锚点不唯一（起 %d / 止 %d）"
                        % (tag, text.count(start_marker), text.count(end_marker)))
        return text
    return text[:a] + new + text[b:]


# ---------------------------------------------------------------- 1) game_addrs
ADDR_BLOCK = """;
; --- [v17] 窗口「背景砖」号的唯一出口（2026-09-11）-------------------------
; `GetBlankTileNum(struct Window *win)` @0x080041BC（反汇编逐指令核对）：
;     b500 push {lr}
;     1c02 adds r2, r0, #0
;     7a90 ldrb r0, [r2, #10]      ; win[0x0A] = textMode
;     2801 cmp  r0, #1             ← 桩覆盖到此为止（8 字节）
;     d009 beq.n 0x080041DA        ← 续跑点 0x080041C4
;     ...
;     8ad0 ldrh r0, [r2, #22]      ; win[0x16] = tileDataStartOffset
;     30d4 adds r0, #212           ; textMode==1 且 fontNum∈{1,2,4,5}
;     bd00 pop {pc}
; 全盘 `bl` 到它的调用点只有 3 个：0x08003ABC / 0x08003C22（Text_ClearWindow
; @0x08003BA8 两条分支）/ 0x08004196（DoScroll_TextMode0）。
; ⚠ 它就是「窗口底色」的砖号来源 —— 从不经过池子，是漏接的第三类消费者。
GetBlankTileNum                        equ 0x080041BC
"""

STUB_BLOCK = """
; 窗口背景砖号 GetBlankTileNum 入口 —— 覆盖 0x080041BC..0x080041C3
;   （push {lr} / adds r2,r0,#0 / ldrb r0,[r2,#10] / cmp r0,#1；续跑 0x080041C4）
;   桩型 = **8B「不碰栈」纯跳转**，与 v13.2/v14/v15 同型；入口 lr = 调用者返回地址，
;   桩不碰 lr ⇒ 跳板的「强制 0」路径可直接 `pop {pc}` 回调用者。
.org GetBlankTileNum
    ldr  r3, =(V17BlankTile_Hook | 1)
    bx   r3
.pool
"""

ENTRY_V17 = """
@ =============================================================================
@ [v17] 窗口「背景砖」号 —— 与文字/框同权的**第三类消费者**（2026-09-11）
@ -----------------------------------------------------------------------------
@ 漏点（用户判定「你调研阶段就漏 hook 点了」—— 成立）：
@   官方「窗口」在屏幕上可见的部分是**两类**，不是一类：
@     ① 框（框图形 + 框 tilemap）—— v12/v14/v15 已接；
@     ② **窗口内容区的底色** —— 由 `GetBlankTileNum` 给出的「空白砖」填出来：
@          · `Text_ClearWindow`（清整窗，两条分支）
@          · `Text_BlankWindowRect`（填矩形）
@          · `DoScroll_TextMode0`（滚动补行）
@        全盘 `bl 0x080041BC` 只有这 3 个调用点（反汇编实证）。
@   ② 的砖号是**硬编码官号**（`win[0x16]`，fontNum∈{1,2,4,5} 再 +212），
@   **从不经过池子** ⇒ 池子满了以后：文字领不到号（不画），② 照样把窗口
@   填成官号砖 ⇒ 屏幕上留下「文字空、UI 不空」的空白块（PokéNav 那几个粉块）。
@
@ 语义（与文本/框完全一致）：**池子连一个砖都给不出 ⇒ 返回 0**
@   ⇒ 3 个调用点填 `paletteNum << 12 | 0` = 0 号砖 = 官方自己的 erase 约定
@   ⇒ 窗口底色也一起空白。
@
@ 桩型 = 8B「不碰栈」纯跳转，覆盖 0x080041BC..0x080041C3（4 条半字）：
@     b500 push {lr} / 1c02 adds r2,r0,#0 / 7a90 ldrb r0,[r2,#10] / 2801 cmp r0,#1
@   跳板**必须重放**这 4 条再落到 0x080041C4；「强制 0」路径用入口那份 lr
@   （桩没碰 lr；跳板 push/pop 成对 ⇒ 栈完全平衡）。
@ =============================================================================
    .global V17BlankTile_Hook
    .thumb_func
    .type V17BlankTile_Hook, %function
    .extern v17_blank_tile_C
V17BlankTile_Hook:
    push    {r4, lr}                   @ 8B：保 lr（返回要用）+ 让出 r4
    adds    r4, r0, #0                 @ r4 = win（C 会砸 r0）
    bl      v17_blank_tile_C           @ → 1 = 照官方走 / 0 = 池子没号，强制空
    adds    r2, r0, #0                 @ r2 = 判定
    adds    r0, r4, #0                 @ r0 = win（两条路径都要）
    pop     {r4}                       @ r4 复原（栈顶还剩入口那份 lr）
    cmp     r2, #0
    beq     BlankTile_ForceZero
    @ —— 照官方走：重放被桩覆盖的 4 条半字，再落到 0x080041C4 ——
    push    {lr}                       @ 重放 0x080041BC
    adds    r2, r0, #0                 @ 重放 0x080041BE
    ldrb    r0, [r2, #10]              @ 重放 0x080041C0（win[0x0A] = textMode）
    cmp     r0, #1                     @ 重放 0x080041C2
    ldr     r3, =0x080041C5            @ 续跑点 0x080041C4（beq.n）—— |1 保 Thumb
    bx      r3
BlankTile_ForceZero:
    movs    r0, #0                     @ 池子没号 ⇒ 官方 erase 约定
    pop     {pc}                       @ 栈顶正是入口那份 lr
    .size V17BlankTile_Hook, .-V17BlankTile_Hook
    .pool

"""

TAC_NEW = """/* ============================================================================
 * v17（2026-09-11）：窗口**背景砖**号的判定口 —— 第三类消费者。
 *
 * 唯一出口 = `GetBlankTileNum` @0x080041BC（entry.s 的 V17BlankTile_Hook 调它）。
 * 它返回官方那个「空白砖」号（`win[0x16]`，fontNum∈{1,2,4,5} 再 +212）；
 * 全盘只有 3 个调用点，全是「把窗口填成底色」：
 *     Text_ClearWindow / Text_BlankWindowRect / DoScroll_TextMode0。
 *
 * 语义与文字、框**完全一致**：池子连一个砖都给不出 ⇒ 返回 0
 *   ⇒ 调用方填 `paletteNum << 12 | 0` = 0 号砖 = 官方自己的 erase 约定
 *   ⇒ 窗口底色也跟着空白。（用户判据：「到顶 UI 和文字都会空白」。）
 *
 * 返回：1 = 照官方走（行为不变）；0 = 强制 0。
 * ⚠ 纯扫描：不取号、不改游标、不进 ours（与 v8_scan_find 同语义，单向收窄）。
 * ==========================================================================*/
int v17_blank_tile_C(uint8_t *win)
{
    uint8_t *tpl;
    const void *vram;
    uint16_t lo, hi;

    if (!win)
        return 1;                       /* 不认识 ⇒ 绝不改官方行为 */
    tpl = *(uint8_t *volatile *)win;    /* win[0] = 模板 */
    if (!tpl)
        return 1;
    vram = (const void *)(uintptr_t)win_u32(tpl, TPL_TILE_DATA);
    if (!vram)
        return 1;
    hi = v8_alloc_hi(tpl[TPL_CHARBASE]);
    lo = v10_pool_lo();
    if (lo >= hi)
        return 0;                       /* 区间本身不存在 */
    return (v8_scan_find(1u, lo, hi, v8_bitmap(), vram) != 0u) ? 1 : 0;
}
"""


def main():
    problems = []
    out = {}

    # ---------------- game_addrs.asm
    t, nl = load(FILES["addrs"])
    if "GetBlankTileNum" in t:
        problems.append("game_addrs.asm: GetBlankTileNum 已存在（补丁可能已应用）")
    t = t.rstrip("\n") + "\n" + ADDR_BLOCK
    out["addrs"] = (t, nl)

    # ---------------- hooks_origin.s
    t, nl = load(FILES["stubs"])
    if "V17BlankTile_Hook" in t:
        problems.append("hooks_origin.s: V17BlankTile_Hook 已存在")
    t = t.rstrip("\n") + "\n" + STUB_BLOCK
    out["stubs"] = (t, nl)

    # ---------------- entry.s
    t, nl = load(FILES["entry"])

    # (a) 删 .extern v8_frame_room
    t = rep(t, "    .extern v8_frame_room\n", "", "entry.s/.extern v8_frame_room",
            problems)

    # (b) 删 v14 std 侧的 v16 关卡
    old_std = """    @ 🔴 v16：槽非 0 也要再过一关 —— 「这个号现在还归池子管吗？」
    @   ⑤ 只在本窗装载时发号，而**有些窗口的装载链根本不调 ⑤**
    @   （领航员：InitWindow → ① → ③）⇒ 它读到的 0x03000514 是别的窗口的残值
    @   ⇒ 框不用过池子就能画 ⇒ 「文字空、UI 独活」的第二个成因。
    @   判定 = 「池子当下还能不能给出一整段 V10_FRAME_SPAN 个连续可用砖」。
    ldr     r2, =0x03000328            @ gTplSlot（① / 姊妹路径 / v13.2 都在维护）
    ldr     r2, [r2]
    cmp     r2, #0
    beq     StdFrameTmap_Erase
    push    {r0, r4, r5, r6}           @ 16B：保 tilemap + 矩形（C 会砸 r0-r3）
    adds    r0, r2, #0                 @ r0 = tpl
    bl      v8_frame_room              @ → r0 = 1（给得出）/ 0（给不出）
    cmp     r0, #0                     @ ⚠ pop 不改标志，cmp 必须排在 pop 前
    pop     {r0, r4, r5, r6}           @ 还原（16B ⇒ 8 对齐不变）
    beq     StdFrameTmap_Erase
"""
    new_std = """    @ 🔴 v16 加的「池子还发不发得出一个整框」第二关（`v8_frame_room`）**已删**
    @   （2026-09-11，用户实测「继续游戏 UI 直接没了」）：它要求 23 个**连续**
    @   可用砖，而官方图形是碎片化的 ⇒ 在池子明明还有空间时也会误判「给不出」
    @   ⇒ 把本来正常的菜单框一起擦掉。判据回退为 ⑤ 自己的判决（槽 == 0）。
"""
    t = rep(t, old_std, new_std, "entry.s/v14-std 的 v16 关卡", problems)

    # (c) 删 v14 dlg 侧的 v16 关卡
    old_dlg = """    @ v16：同一个「号还在不在池子里」关 —— 与标准框完全一致。
    ldr     r1, =0x03000328            @ gTplSlot
    ldr     r1, [r1]
    cmp     r1, #0
    beq     DlgFrameTmap_Erase
    @ ⚠ v4T 的 Thumb 没有 `pop {r4,lr}`（无 32 位 Thumb）⇒ 用 r5 手工保 lr。
    push    {r4, r5}                   @ 8B：r4 = win，r5 = lr
    adds    r4, r0, #0                 @ r4 = win（erase 路径要用 r0 = win）
    mov     r5, lr
    adds    r0, r1, #0                 @ r0 = tpl
    bl      v8_frame_room
    adds    r2, r0, #0                 @ r2 = 1 / 0
    adds    r0, r4, #0                 @ r0 = win
    mov     lr, r5                     @ 还原 lr
    pop     {r4, r5}                   @ pop 不改标志 ⇒ cmp 必须排在后面
    cmp     r2, #0
    beq     DlgFrameTmap_Erase
"""
    new_dlg = """    @ 🔴 v16 的第二关（`v8_frame_room`）已删，理由同标准框那处
    @   （23 个连续砖的判据会误擦正常菜单框）。判据 = ⑥ 自己的判决（槽 == 0）。
"""
    t = rep(t, old_dlg, new_dlg, "entry.s/v14-dlg 的 v16 关卡", problems)

    # (d) 追加 V17
    if "V17BlankTile_Hook" in t:
        problems.append("entry.s: V17BlankTile_Hook 已存在")
    if ".end" not in t:
        problems.append("entry.s: 找不到 .end")
    else:
        t = t.replace(".end", ENTRY_V17 + ".end", 1)
    out["entry"] = (t, nl)

    # ---------------- tile_alloc.h
    t, nl = load(FILES["tah"])
    t = rep(t, "int v8_frame_room(uint8_t *tpl);",
            "/* [v17] 窗口**背景砖**号判定：1 = 照官方走，0 = 池子给不出 ⇒ 强制 0 号砖。\n"
            " *     被 entry.s 的 V17BlankTile_Hook（GetBlankTileNum @0x080041BC）调用。 */\n"
            "int v17_blank_tile_C(uint8_t *win);",
            "tile_alloc.h/v8_frame_room 声明", problems)
    out["tah"] = (t, nl)

    # ---------------- tile_alloc.c：整段替换 v8_frame_room
    t, nl = load(FILES["tac"])
    key = "int v8_frame_room(uint8_t *tpl)"
    i = t.find(key)
    if i < 0:
        problems.append("tile_alloc.c: 找不到 v8_frame_room 本体")
    else:
        # 往前吃掉注释块
        c = t.rfind("/* ===", 0, i)
        if c < 0:
            problems.append("tile_alloc.c: v8_frame_room 前找不到注释块起点")
        # 往后找到函数结束（首次出现的行首 "\n}\n"）
        e = t.find("\n}\n", i)
        if e < 0:
            problems.append("tile_alloc.c: v8_frame_room 函数体结束定位失败")
        if not problems:
            t = t[:c] + TAC_NEW + t[e + 3:]
    out["tac"] = (t, nl)

    # ---------------- build_sh_equiv.sh / build.bat
    t, nl = load(FILES["sh"])
    t = rep(t, "           V15LoadPal_Hook V15LoadStyle_Hook; do",
            "           V15LoadPal_Hook V15LoadStyle_Hook V17BlankTile_Hook; do",
            "build_sh_equiv.sh 符号表", problems)
    out["sh"] = (t, nl)

    t, nl = load(FILES["bat"])
    t = rep(t, "V15LoadPal_Hook V15LoadStyle_Hook) do (",
            "V15LoadPal_Hook V15LoadStyle_Hook V17BlankTile_Hook) do (",
            "build.bat 符号表", problems)
    out["bat"] = (t, nl)

    # ---------------- 落盘
    if problems:
        print("!! 未写盘（锚点不匹配）：")
        for p in problems:
            print("   -", p)
        return 1

    for k, (text, nl) in out.items():
        save(FILES[k], text, nl)
        print("OK  %-46s %6d bytes  nl=%s"
              % (os.path.relpath(FILES[k], HOOK), len(text.encode("utf-8")),
                 "CRLF" if nl == "\r\n" else "LF"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
