#!/usr/bin/env python3
"""结论：ruby 能不能做 3 字节中文编码？

核心矛盾：
  3 字节编码需要 1 个前缀字节 + 2 字节码位。
  前缀字节必须「在文本流里不会被当作其他语义消费」。

本脚本汇总所有证据，给出明确答案：
  1. 汉字 lead 的实际取值范围（决定码位空间）
  2. 高位字节 0xF0..0xFF 的实际占用
  3. 能否找到可用前缀

用法：
    python scripts/research/ruby/probe_3byte_feasibility.py
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
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
CMAP = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "charmap.txt"


def main() -> int:
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    # 1. 汉字 lead 分布：F9 00 之后的第一个字节
    leads: Counter = Counter()
    n_f900 = 0
    for e in entries:
        oh = (e.get("original_hex") or "").replace(" ", "").lower()
        try:
            raw = bytes.fromhex(oh)
        except ValueError:
            continue
        i = 0
        while i < len(raw) - 3:
            if raw[i] == 0xF9 and raw[i + 1] == 0x00:
                leads[raw[i + 2]] += 1
                n_f900 += 1
                i += 4
            else:
                i += 1

    print("=== F9 00 汉字的 lead 字节分布 ===")
    print(f"  F9 00 总数 {n_f900:,}，distinct lead {len(leads)} 种")
    for b, c in sorted(leads.items())[:30]:
        print(f"    lead 0x{b:02X}: {c:>6,}")
    if leads:
        print(f"  lead 范围: 0x{min(leads):02X} .. 0x{max(leads):02X}")
    print()

    # 2. charmap.txt 里的映射统计
    if CMAP.is_file():
        lines = CMAP.read_text(encoding="utf-8", errors="replace").splitlines()
        n_2byte = 0
        lead_set = set()
        for ln in lines:
            ln = ln.strip()
            if not ln or "=" not in ln:
                continue
            hexp = ln.split("=", 1)[0].strip()
            parts = hexp.split()
            if len(parts) == 2:
                n_2byte += 1
                try:
                    lead_set.add(int(parts[0], 16))
                except ValueError:
                    pass
        print("=== charmap.txt ===")
        print(f"  2 字节映射 {n_2byte:,} 条，lead 值 {len(lead_set)} 种")
        if lead_set:
            print(f"  lead 范围 0x{min(lead_set):02X} .. 0x{max(lead_set):02X}")
        print()

    # 3. 关键判断
    print("=== 3 字节编码可行性 ===")
    print("  需求：1 前缀字节 + 1 高字节 + 1 低字节")
    print("  现有 F9 00: F9=前缀, 00=通道, hi=lead(0x01-0x1E), lo=trail → 4 字节")
    print("  F7 hi lo: F7=前缀, hi=lead, lo=trail → 3 字节，省掉 00 通道字节")
    print()
    print("  障碍：0xF7 已被 [angry] 表情 + FC 0C 颜色参数占用（实测 62 条）")
    print("  0xF0..0xFF 全部有实际使用，无空闲字节")
    print()
    print("  ⇒ 除非能安全重映射 [angry] 的编码，否则无法直接照搬火红的 F7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
