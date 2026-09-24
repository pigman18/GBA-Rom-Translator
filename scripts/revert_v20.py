#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""revert_v20.py — 精确撤销 v20（常规 UI 的 LZ77→VRAM 装载总闸）。

为什么撤（2026-09-11 用户实测 + 源码归因）：
    用户：「背包进入卡死，领航员进入重启」。
    `tools/pokeruby/src/party_menu.c:623`
        DmaFill16Large(3, 0, (void *)(VRAM + 0x0), VRAM_SIZE, 0x1000);
    ⇒ 这些 UI **每进一次就整块清 VRAM，再按固定顺序逐项重装**。
    v20 的「在 LZ 装载点把目标区域清 0」正好插在这个序中间，
    把人家的中间数据清掉 ⇒ 背包卡死 / 领航员重启。
    不是判据错，是**手法与生命周期打架**。

手法：复用 `apply_v20.py` 里的**模块级常量**做反向替换（保证逐字节还原），
    每处断言 count == 1，不猜测、不模糊删除。

🔴 与 revert_v19.py 的关键差别：v20 的三处追加都是**在文件末尾 append**，
   所以反向就是「删掉末尾那一整段」，而不是 re.sub 掉中间某段。
   末尾段的确切内容由 apply_v20 的常量提供，避免手抄出错。

用法：python scripts/revert_v20.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("apply_v20", os.path.join(HERE, "apply_v20.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)          # main 受 __main__ 保护，import 无副作用

TAG = "[v20 撤销]"
ROOT = A.ROOT
HOOK = A.HOOK


def read(p):
    with open(p, "rb") as f:
        b = f.read()
    return b.decode("utf-8"), ("\r\n" in b.decode("utf-8"))


def write(p, text, crlf=False):
    out = text.replace("\r\n", "\n")
    if crlf:
        out = out.replace("\n", "\r\n")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(out)


def cut_tail(path, block, tag):
    """删掉文件末尾由 apply_v20 append 上去的那一段。"""
    text, crlf = read(path)
    payload = block.lstrip("\n")                       # append_block 写入的正是这个
    n = text.count(payload)
    assert n == 1, "%s %s: 末尾段 count=%d（期望 1）" % (TAG, tag, n)
    assert text.endswith(payload), "%s %s: 末尾段不在文件末尾" % (TAG, tag)
    write(path, text[: -len(payload)], crlf)
    rel = os.path.relpath(path, ROOT)
    print("OK   %-44s -末尾段(%d 字符)" % (rel, len(payload)))


def sub_once(path, old, new, tag):
    text, crlf = read(path)
    n = text.count(old)
    assert n == 1, "%s %s: count=%d（期望 1）" % (TAG, tag, n)
    write(path, text.replace(old, new, 1), crlf)
    rel = os.path.relpath(path, ROOT)
    print("OK   %-44s -1 处" % rel)


def main() -> int:
    # ---------------------------------------------- 1. game_addrs.asm（末尾 equ 块）
    p1 = os.path.join(HOOK, "game_addrs.asm")
    cut_tail(p1, A.BLOCK_EQU, "game_addrs.asm equ 块")

    # ---------------------------------------------- 2. hooks_origin.s（末尾桩块）
    p2 = os.path.join(HOOK, "src", "text", "hooks_origin.s")
    cut_tail(p2, A.BLOCK_STUB, "hooks_origin.s 桩块")

    # ---------------------------------------------- 3. entry.s（跳板插在 .end 之前）
    p3 = os.path.join(HOOK, "src", "text", "entry.s")
    sub_once(p3, A.BLOCK_THUNK + "\n.end", "\n.end", "entry.s 跳板块")

    # ---------------------------------------------- 4. build_sh_equiv.sh（3 处，逆序撤）
    p4 = os.path.join(HOOK, "build_sh_equiv.sh")
    sub_once(p4, "V17BlankTile_Hook V20LzUi_Hook; do",
             "V17BlankTile_Hook; do", "sh 符号表")
    sub_once(p4, "  $BUILD/win_alloc.o \\\n  $BUILD/lz_ui.o \\",
             "  $BUILD/win_alloc.o \\", "sh 链接行")
    sub_once(p4,
             "$CC $CFLAGS  $TEXT/lz_ui.c                    -o $BUILD/lz_ui.o\n"
             "$CC $CFLAGS  $TEXT/win_alloc.c",
             "$CC $CFLAGS  $TEXT/win_alloc.c", "sh 编译行")
    t, _ = read(p4)
    assert "lz_ui" not in t and "V20LzUi" not in t, TAG + " build_sh_equiv.sh 仍有残留"

    # ---------------------------------------------- 5. build.bat（3 处，逆序撤）
    p5 = os.path.join(HOOK, "build.bat")
    if os.path.exists(p5):
        sub_once(p5, "V17BlankTile_Hook V20LzUi_Hook)",
                 "V17BlankTile_Hook)", "bat 符号表")
        sub_once(p5, "  %BUILD%/win_alloc.o ^\n  %BUILD%/lz_ui.o ^",
                 "  %BUILD%/win_alloc.o ^", "bat 链接行")
        sub_once(p5,
                 "%CC% %CFLAGS% %TEXT%\\lz_ui.c -o %BUILD%\\lz_ui.o\n"
                 "%CC% %CFLAGS% %TEXT%\\win_alloc.c -o %BUILD%\\win_alloc.o",
                 "%CC% %CFLAGS% %TEXT%\\win_alloc.c -o %BUILD%\\win_alloc.o",
                 "bat 编译行")
        t, _ = read(p5)
        assert "lz_ui" not in t and "V20LzUi" not in t, TAG + " build.bat 仍有残留"
    else:
        print("SKIP build.bat（不存在）")

    # ---------------------------------------------- 6. 删 v20 新文件
    for p in (os.path.join(HOOK, "include", "lz_ui.h"),
              os.path.join(HOOK, "include", "lz_ui_sites.h"),
              os.path.join(HOOK, "src", "text", "lz_ui.c")):
        if os.path.exists(p):
            os.remove(p)
            print("DEL  %s" % os.path.relpath(p, ROOT))
        else:
            print("SKIP %s（已不存在）" % os.path.relpath(p, ROOT))

    print()
    print("v20 已完整撤销。下一步必须重新 build 并核对 game.bin 回到 11548 B。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
