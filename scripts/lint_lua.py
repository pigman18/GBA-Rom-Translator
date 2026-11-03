#!/usr/bin/env python3
"""粗粒度 Lua 结构检查：括号配对 / function-end 计数。

用途：mGBA 的 Lua 一旦语法错就**静默退出**（连 scene.log 都不生成），
      症状是「模拟器跑满超时、目录空的」，很容易被误判成场景逻辑卡死。
      本地没有 lua 解释器，所以用这个脚本先排掉最基本的语法问题。

用法：python scripts/lint_lua.py bot/bot.lua bot/scenes/**/_lib.lua
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def strip_noise(src: str) -> str:
    """去掉注释和字符串字面量，只留结构字符。"""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # 长括号字符串 [[ ]] / [=[ ]=]
        if c == "[":
            m = re.match(r"\[(=*)\[", src[i:])
            if m:
                eq = m.group(1)
                close = "]" + eq + "]"
                j = src.find(close, i + len(m.group(0)))
                i = (j + len(close)) if j >= 0 else n
                out.append('""')
                continue
        # 行注释
        if src.startswith("--", i):
            m = re.match(r"--\[(=*)\[", src[i:])
            if m:
                eq = m.group(1)
                close = "]" + eq + "]"
                j = src.find(close, i + len(m.group(0)))
                i = (j + len(close)) if j >= 0 else n
                continue
            j = src.find("\n", i)
            i = j if j >= 0 else n
            continue
        if c in "\"'":
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    j += 1
                    break
                j += 1
            i = j
            out.append('""')
            continue
        out.append(c)
        i += 1
    return "".join(out)


def check(path: Path) -> int:
    src = path.read_text(encoding="utf-8", errors="replace")
    code = strip_noise(src)

    depth = 0
    bad_line = None
    for ln, line in enumerate(code.splitlines(), 1):
        for ch in line:
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth -= 1
                if depth < 0 and bad_line is None:
                    bad_line = ln
    # function/end 计数（含 if/for/while/do 的 end，只能粗判）
    nfun = len(re.findall(r"\bfunction\b", code))
    nend = len(re.findall(r"\bend\b", code))

    ok = True
    print(f"{path}")
    if depth != 0:
        print(f"  [ERR] 括号深度 = {depth}（应为 0）"
              + (f"，首次负深度在第 {bad_line} 行" if bad_line else ""))
        ok = False
    if nend < nfun:
        print(f"  [ERR] function={nfun} 但 end={nend} ⇒ 有明显缺 end")
        ok = False

    # ★ 顶层语句存在性检查（2026-11-03 加）。
    #   为什么必须加：我曾把 `else` 分支和两个 `end` 误删，
    #   括号仍然平衡、function/end 计数也过得去，但
    #   `stop(...)` 与后面的 `if shots == 0 ... end` 被卷进了 for 循环体里。
    #   那是**语义错，不是语法错**，模拟器不会报错，只会一直跑不动。
    #   对策：点名几个必须出现的语句，缺一个就报。
    #   ⚠ 要在**原始源码**里找（strip 之后字符串字面量被替换成 ""，
    #     带引号的 marker 永远匹配不上 —— 这里踩过一次）。
    for marker in REQUIRED_TOP_LEVEL.get(path.name, []):
        if marker not in src:
            print(f"  [ERR] 缺少语句：{marker}")
            ok = False

    if ok:
        print(f"  OK  括号平衡；function={nfun} end={nend}")
    return 0 if ok else 1


# 每个文件必须出现的顶层语句（防止「结构合法但语义被吞」）
REQUIRED_TOP_LEVEL = {
    "bot.lua": [
        "if shots == 0 then stop(1,",
        "if total_frames * 3 > MAX_FRAMES then",
        '[ERR] unknown act at step %d',
        "advance = function(fr)",
        'callbacks:add("keysRead"',
        'callbacks:add("frame"',
    ],
    "_lib.lua": [
        "return M",
    ],
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rc = 0
    for p in sys.argv[1:]:
        rc |= check(Path(p))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
