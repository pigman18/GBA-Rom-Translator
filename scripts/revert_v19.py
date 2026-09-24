#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revert_v19.py — 精确撤销 v19（LZ77→VRAM 装载总闸）。

为什么撤：v19 = 装备「门 LZ77UnCompVram / dst 落 VRAM 就清 0」的**总闸**，
而 `docs/UI_HOOK_SURVEY.md` §4 早已把这一路判死：

    | ② 一次 LZ 总闸 | 门 LZDecompressVram，dest 落在屏幕块区就填 0 |
    |                | **不要**：会把地图/其它 LZ 资源一起关掉 |

2026-09-12 反汇编实证（`scripts/lz77_args.py`）：
    · `0811E28A  src=0x087F9D0C size=0x4000(512砖) dst=0x06000000`  ← 野外 primary tileset
    · `080791BA  src=0x0836D268 size=0x2700(312砖) dst=0x06000000`  ← 信息页美术
  两者**落点同一个地址** ⇒ 按 dst 根本分不出 UI 与地图 ⇒ 总闸必然连地图一起清。

手法：直接复用 `apply_v19.py` 里的字符串常量做反向替换（保证逐字节还原），
    并断言每处 `count == 1`，不做猜测。
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("apply_v19", os.path.join(HERE, "apply_v19.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)          # 只有常量与函数定义，main 受 __main__ 保护

TAG = "[v19 撤销]"


def rm1(text: str, old: str, tag: str) -> str:
    n = text.count(old)
    assert n == 1, "%s %s: count=%d（期望 1）" % (TAG, tag, n)
    return text.replace(old, "")


def rep1(text: str, old: str, new: str, tag: str) -> str:
    n = text.count(old)
    assert n == 1, "%s %s: count=%d（期望 1）" % (TAG, tag, n)
    return text.replace(old, new)


def main() -> int:
    # ------------------------------------------------ 1. game_addrs.asm
    t, crlf = A.load(A.ADDRS)
    t = rm1(t, A.ADDRS_BLOCK, "game_addrs.asm equ 块")
    A.save(A.ADDRS, t, crlf)
    print("OK   game_addrs.asm        -equ 块")

    # ------------------------------------------------ 2. hooks_origin.s
    t, crlf = A.load(A.STUBS)
    t = rm1(t, A.STUB_BLOCK, "hooks_origin.s 桩块")
    A.save(A.STUBS, t, crlf)
    print("OK   hooks_origin.s        -桩")

    # ------------------------------------------------ 3. entry.s
    t, crlf = A.load(A.ENTRY)
    t = rep1(t, "\n" + A.ENTRY_BLOCK + ".end\n", "\n.end\n", "entry.s 跳板块")
    A.save(A.ENTRY, t, crlf)
    print("OK   entry.s               -跳板")

    # ------------------------------------------------ 4/5. 删新文件
    for p in (A.HDR, A.SRC):
        if os.path.exists(p):
            os.remove(p)
            print("DEL  %s" % os.path.relpath(p, A.ROOT))
        else:
            print("SKIP %s（已不存在）" % os.path.relpath(p, A.ROOT))

    # ------------------------------------------------ 6. build_sh_equiv.sh
    t, crlf = A.load(A.SH)
    t = rm1(t,
            "$CC $CFLAGS  $TEXT/lz_gate.c                     -o $BUILD/lz_gate.o\n",
            "sh 编译行")
    t = rm1(t, "  $BUILD/lz_gate.o \\\n", "sh 链接行")
    t = rep1(t, "V17BlankTile_Hook V19LzGate_Hook; do", "V17BlankTile_Hook; do",
             "sh 符号表")
    assert "lz_gate" not in t and "V19LzGate" not in t, TAG + " sh 仍有残留"
    A.save(A.SH, t, crlf)
    print("OK   build_sh_equiv.sh     -3 处")

    # ------------------------------------------------ 7. build.bat
    t, crlf = A.load(A.BAT)
    t = rm1(t,
            "echo === Compiling text\\lz_gate.c (v19 LZ gate) ===\n"
            "%CC% %CFLAGS% %TEXT%\\lz_gate.c -o %BUILD%\\lz_gate.o\n"
            "if errorlevel 1 exit /b 1\n"
            "\n",
            "bat 编译块")
    t = rm1(t, "  %BUILD%/lz_gate.o ^\n", "bat 链接行")
    t = rep1(t, "V17BlankTile_Hook V19LzGate_Hook)", "V17BlankTile_Hook)",
             "bat 符号表")
    assert "lz_gate" not in t and "V19LzGate" not in t, TAG + " bat 仍有残留"
    A.save(A.BAT, t, crlf)
    print("OK   build.bat             -3 处")

    print("\nv19 已完整撤销。下一步必须重新 build 并核对 game.bin 回到 11548 B。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
