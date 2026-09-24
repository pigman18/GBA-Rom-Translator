#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""apply_v20.py — 一次性打入 v20（常规 UI 的 LZ77→VRAM 装载总闸）。

改 5 个文件（全部用**精确哨兵**判定，幂等；保留各文件原换行风格）：
  1) hook/game_addrs.asm        追加 `LZ77UnCompVram equ 0x081B1298`
  2) hook/src/text/hooks_origin.s  追加 8B 桩（armips 语法，`;` 注释）
  3) hook/src/text/entry.s      在 `.end` 前插入跳板（GNU as 语法，`@` 注释）
  4) hook/build_sh_equiv.sh     编译行 + 链接行 + game_syms.asm 符号清单
  5) hook/build.bat             同上（存在才改）

🔴 哨兵必须命中**要改的那一行本身**，不能用裸名字：
   v19 曾把哨兵写成裸 `"LZ77UnCompVram"`，而 game_addrs.asm 第 77 行本来就有一条
   **注释**含这个名字 ⇒ `if s not in text` 为假 ⇒ 整块被静默跳过，equ 从没写进去。
   这次哨兵用 `"LZ77UnCompVram" + 26*空格 + "equ"`（认 equ 那一行）。

用法：python scripts/apply_v20.py [--check]
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook")

# ---- 哨兵 -----------------------------------------------------------------
SENT_EQU = "LZ77UnCompVram" + " " * 26 + "equ 0x081B1298"
SENT_ORG = ".org LZ77UnCompVram"
SENT_THUNK = "V20LzUi_Hook:"
SENT_SH = "$TEXT/lz_ui.c"
SENT_BAT = "lz_ui.c"

# ---- 1) equ ---------------------------------------------------------------
BLOCK_EQU = """
; --- [v20] 常规 UI 的 LZ77→VRAM 装载总闸（2026-09-12）------------------------
; `LZ77UnCompVram` @0x081B1298 = `12df 7047` = `svc 0x12 ; bx lr`（BIOS 蹦床）
; `LZ77UnCompWram` @0x081B129C = `11df 7047` = `svc 0x11 ; bx lr`
; 原盘实测：`bl 0x081B1298` **118 处**、`bl 0x081B129C` **42 处**。
; 常规 UI（队伍菜单 / 宝可梦信息页 / 领航员 / PC 箱子 / 简易聊天）的**图形**
; 不经过窗口分配器，统统从这里解压进 VRAM 的固定地址 ——
; 这正是用户说的「本来就是多个点申请 tile」背后的收敛层。
; 🔴 判据只能用**调用点 lr**：`0x06000000` 上野外 primary tileset 与信息页美术
;    字节级同址（0811E28A / 080791BA）⇒ 按 dst 必误伤地图（v19 已撤，见
;    docs/UI_LZ_SITES.md §4）；按 src 也不行（运行时 src = tileset->tiles）。
; ⚠ 桩吃 0x081B1298..9F 这 8 字节（**两条蹦床一起**）：`ldr r3,[pc,#0]` 的池子
;   只能落在 4 字节内 = 正好 129C，放更远会写坏别的代码。跳板按 dst 还原
;   写粒度（Vram 半字 / Wram 字节）。紧邻的 0x081B12A0(svc 0x0F, 5 处调用)
;   与 0x081B12A4(svc 0x15, 13 处) 不能吃。
LZ77UnCompVram                         equ 0x081B1298
"""

# ---- 2) 桩（armips）-------------------------------------------------------
BLOCK_STUB = """
; --- [v20] 常规 UI 的 LZ77→VRAM 装载总闸（2026-09-12）------------------------
; 用户判定「常规 UI 都没接管到」⇒ 根因是那些 UI 的图形不走窗口分配器，
; 而由 BIOS LZ77UnCompVram 直接解压到 VRAM 固定地址（全盘 118 处 bl）。
; 桩型 = **8B「不碰栈」纯跳转**（ldr r3 / bx r3 / .pool），与 v13.2/v14/v15/v17 同型。
; `bx`（不是 bl）⇒ **不改 lr** ⇒ 进跳板时 lr = 调用者在 bl 之后要返回的地址。
; 跳板用 `mov r2, lr` 把它当「调用点」查白名单（include/lz_ui_sites.h，104 处）。
; ⚠ 覆盖 0x081B1298..0x081B129F：LZ77UnCompVram + LZ77UnCompWram 两条蹦床。
;   两者**解出的字节内容完全一致**，只差写粒度（VRAM 必须半字写）⇒
;   跳板按 dst 决定用 svc 0x12 还是 svc 0x11，字节级永远正确。
.org LZ77UnCompVram
    ldr  r3, =(V20LzUi_Hook | 1)
    bx   r3
.pool
"""

# ---- 3) 跳板（GNU as）-----------------------------------------------------
BLOCK_THUNK = """
@ --- [v20] 常规 UI 的 LZ77→VRAM 装载总闸（2026-09-12）----------------------
@ 桩在 0x081B1298（8 字节，吃掉 LZ77UnCompVram 与 LZ77UnCompWram 两条蹦床）。
@ 桩用 `bx` ⇒ 进来时 lr = **调用者**的返回地址（`bl` 指令地址 + 4）= 调用点。
@
@ 栈净额：入口 push {r4,lr} + push {r0,r1} = 4 字；出口 pop {r0,r1} + pop {r4,pc}
@         = 4 字 ⇒ 净 0（被覆盖的两条蹦床本身不碰栈）。
@ 三条出口都是 `pop {r4, pc}` ⇒ 弹回的正是入口那份 lr ⇒ 等价于原体的 `bx lr`。
    .global V20LzUi_Hook
    .thumb_func
    .type V20LzUi_Hook, %function
    .extern v20_lz_ui_C
V20LzUi_Hook:
    push    {r4, lr}                   @ 保入口 lr（同时也是给 C 的 site 来源）
    mov     r2, lr                     @ r2 = site（调用点）—— 必须在 bl 之前取
    push    {r0, r1}                   @ 保参数：r0=src r1=dst（C 会砸 r0-r3）
    bl      v20_lz_ui_C                @ → 0 = 已清空 / 1 = svc 0x12 / 2 = svc 0x11
    adds    r4, r0, #0                 @ r4 = 判定（r0 马上要被还原冲掉）
    pop     {r0, r1}                   @ 还原参数（下面真正的 SWI 要用）
    cmp     r4, #0
    beq     LzUi_Blank
    cmp     r4, #2
    beq     LzUi_Wram
    svc     #0x12                      @ 官方 LZ77UnCompVram（半字写，VRAM 必须）
    pop     {r4, pc}
LzUi_Wram:
    svc     #0x11                      @ 官方 LZ77UnCompWram（字节写）
    pop     {r4, pc}
LzUi_Blank:
    movs    r0, #0                     @ 目标 VRAM 区已被清成 0 号砖 ⇒ 不再解压
    pop     {r4, pc}
    .size V20LzUi_Hook, .-V20LzUi_Hook
    .pool
"""


def read(p: str):
    with open(p, "rb") as f:
        b = f.read()
    return b.decode("utf-8"), ("\r\n" in b.decode("utf-8"))


def write(p: str, text: str, crlf: bool = False):
    out = text.replace("\r\n", "\n")
    if crlf:
        out = out.replace("\n", "\r\n")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(out)


def patch_check(path: str, sentinel: str) -> bool:
    text, _ = read(path)
    return sentinel in text


def sub_once(path: str, old: str, new: str) -> bool:
    text, crlf = read(path)
    if old not in text:
        print("  !! 找不到锚点：%s" % repr(old[:60]))
        return False
    if text.count(old) != 1:
        print("  !! 锚点不唯一（%d 次）：%s" % (text.count(old), repr(old[:60])))
        return False
    write(path, text.replace(old, new, 1), crlf)
    print("  ok  %s" % os.path.relpath(path, ROOT))
    return True


def append_block(path: str, block: str) -> bool:
    text, crlf = read(path)
    if not text.endswith("\n"):
        text += "\n"
    write(path, text + block.lstrip("\n"), crlf)
    print("  ok  %s" % os.path.relpath(path, ROOT))
    return True


def main() -> int:
    check = "--check" in sys.argv
    ok = True

    # ---- 1) equ
    p1 = os.path.join(HOOK, "game_addrs.asm")
    if patch_check(p1, SENT_EQU):
        print("[1/5] game_addrs.asm 已有 v20 equ，跳过")
    elif check:
        print("[1/5] game_addrs.asm 缺 v20 equ")
        ok = False
    else:
        print("[1/5] game_addrs.asm 追加 equ")
        ok &= append_block(p1, BLOCK_EQU)

    # ---- 2) 桩
    p2 = os.path.join(HOOK, "src", "text", "hooks_origin.s")
    if patch_check(p2, SENT_ORG):
        print("[2/5] hooks_origin.s 已有 v20 桩，跳过")
    elif check:
        print("[2/5] hooks_origin.s 缺 v20 桩")
        ok = False
    else:
        print("[2/5] hooks_origin.s 追加桩")
        ok &= append_block(p2, BLOCK_STUB)

    # ---- 3) 跳板（插在 .end 之前）
    p3 = os.path.join(HOOK, "src", "text", "entry.s")
    if patch_check(p3, SENT_THUNK):
        print("[3/5] entry.s 已有 v20 跳板，跳过")
    elif check:
        print("[3/5] entry.s 缺 v20 跳板")
        ok = False
    else:
        print("[3/5] entry.s 插入跳板")
        ok &= sub_once(p3, "\n.end", BLOCK_THUNK + "\n.end")

    # ---- 4) build_sh_equiv.sh
    p4 = os.path.join(HOOK, "build_sh_equiv.sh")
    if patch_check(p4, SENT_SH):
        print("[4/5] build_sh_equiv.sh 已有 v20，跳过")
    elif check:
        print("[4/5] build_sh_equiv.sh 缺 v20")
        ok = False
    else:
        print("[4/5] build_sh_equiv.sh 加 lz_ui.c")
        ok &= sub_once(p4,
                       "$CC $CFLAGS  $TEXT/win_alloc.c",
                       "$CC $CFLAGS  $TEXT/lz_ui.c                    -o $BUILD/lz_ui.o\n"
                       "$CC $CFLAGS  $TEXT/win_alloc.c")
        ok &= sub_once(p4, "  $BUILD/win_alloc.o \\",
                       "  $BUILD/win_alloc.o \\\n  $BUILD/lz_ui.o \\")
        ok &= sub_once(p4, "V17BlankTile_Hook; do",
                       "V17BlankTile_Hook V20LzUi_Hook; do")

    # ---- 5) build.bat
    p5 = os.path.join(HOOK, "build.bat")
    if os.path.exists(p5):
        if patch_check(p5, SENT_BAT):
            print("[5/5] build.bat 已有 v20，跳过")
        elif check:
            print("[5/5] build.bat 缺 v20")
            ok = False
        else:
            print("[5/5] build.bat 加 lz_ui.c")
            # ⚠ 锚点必须带 %CC%：第 63 行的 `echo === Compiling text\win_alloc.c`
            #   也含 "win_alloc.c"，裸锚点会不唯一。
            ok &= sub_once(
                p5,
                "%CC% %CFLAGS% %TEXT%\\win_alloc.c -o %BUILD%\\win_alloc.o",
                "%CC% %CFLAGS% %TEXT%\\lz_ui.c -o %BUILD%\\lz_ui.o\n"
                "%CC% %CFLAGS% %TEXT%\\win_alloc.c -o %BUILD%\\win_alloc.o")
            ok &= sub_once(p5, "  %BUILD%/win_alloc.o ^",
                           "  %BUILD%/win_alloc.o ^\n  %BUILD%/lz_ui.o ^")
            ok &= sub_once(p5, "V17BlankTile_Hook)",
                           "V17BlankTile_Hook V20LzUi_Hook)")
    else:
        print("[5/5] build.bat 不存在，跳过")

    print()
    print("== apply_v20 %s ==" % ("OK" if ok else "**有问题**"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
