#!/usr/bin/env python3
"""核对定长名称表的「槽结构」：定长 stride 还是变长 FF 分隔。

决定整表搬走时能否直接放大：
  定长 stride（每项固定 N 字节，不足补 00）
    → 搬走时不能改 stride（遍历循环用 index*stride 硬算）
    → 中文超长项必须转成指针，或整表改成变长（需同时改遍历代码）
  变长 FF 分隔（每项以 FF 结尾，下一项紧跟）
    → 搬走时直接放大即可，无需改遍历代码

方法：用 translate.build.json 的 original_hex 实测
  - 相邻条目地址差是否恒等于 stride
  - 每项是否以 FF 结尾
  - 项内首个 FF 之后是否还有非零字节（有 → 是定长补位）

用法：
    python scripts/research/ruby/probe_table_slot_shape.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

POINTER_OFFSET = 0x08000000
TARGETS = ["招式名", "特性名", "属性名", "道具名", "图鉴分类名", "秘密基地装饰名", "树果名", "性格名"]


def main() -> int:
    rom = ROM.read_bytes()
    data = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    mods = (json.loads(TEXTS.read_text(encoding="utf-8")).get("modules") or {})

    for mod in TARGETS:
        es = [e for e in entries if e.get("module") == mod]
        if not es:
            continue
        meta = mods.get(mod) or {}
        read = meta.get("read") or {}
        stride = int(read.get("stride") or 0)
        size = int(read.get("entry_size") or 0)

        addrs = []
        for e in es:
            try:
                a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
            except ValueError:
                continue
            addrs.append(a - POINTER_OFFSET if a >= POINTER_OFFSET else a)
        addrs.sort()
        gaps = Counter(b - a for a, b in zip(addrs, addrs[1:]))

        # 每项原文里的 FF 位置
        ff_at_end = 0
        ff_mid = 0
        raw_lens = Counter()
        for e in es:
            try:
                b = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            if not b:
                continue
            raw_lens[len(b)] += 1
            first_ff = b.find(0xFF)
            if first_ff < 0:
                ff_mid += 1
                continue
            tail = b[first_ff + 1:]
            if tail and any(t != 0 and t != 0xFF for t in tail):
                ff_mid += 1
            else:
                ff_at_end += 1

        print(f"=== {mod} ===  {len(es)} 条  配置 stride={stride} entry_size={size}")
        print(f"  相邻地址差（前5）: " + ", ".join(f"{g}B×{c}" for g, c in gaps.most_common(5)))
        print(f"  原文长度分布（前5）: " + ", ".join(f"{l}B×{c}" for l, c in raw_lens.most_common(5)))
        print(f"  FF 后仅补零/填充: {ff_at_end}    FF 后还有内容: {ff_mid}")

        # 判定
        if stride and gaps and gaps.most_common(1)[0][0] == stride:
            shape = f"定长 stride={stride}（地址差恒等于 stride）"
        elif ff_at_end > ff_mid * 3:
            shape = "变长 FF 分隔（项后紧跟下一项）"
        else:
            shape = "混合/不确定"
        print(f"  ⇒ 槽结构: {shape}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
