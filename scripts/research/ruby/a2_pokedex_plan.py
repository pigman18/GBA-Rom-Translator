#!/usr/bin/env python3
"""图鉴分类名：真实容量重算 + 方案选择。

修正后的事实：
  stride=28, name_offset=0, 名字用 0x00 结尾（eos=0）
  **名字可用宽度只有 6 字节**（元数据从 +6 开始，385/386 项）

中文编码 F9 00 hi lo = 4B/字 + 1B 结尾：
  1 字 = 5B ✓
  2 字 = 9B ✗

原文最长 6B，所以原版日文最多 6 个字符（单字节编码）。
中文里 6 字节只够 1 个汉字 + 结尾，而图鉴分类名大多是 2-4 个汉字。

⇒ 6 字节根本不够，必须放大 stride 或换结构。

候选：
  A. 放大 stride：28 → 56（×2），代码的 ×28 需改
  B. 变长 + 指针数组：改代码为读指针
  C. 缩句：压到 1 字（如 '种子' → '种'）—— 用户禁止优先用

先算放大 stride 到多少够用。

用法：
    python scripts/research/ruby/a2_pokedex_plan.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    es = [e for e in d.get("entries") or []
          if e.get("module") == "图鉴分类名"
          and e.get("type") == "replace" and e.get("phrase_code") is not None]
    print(f"图鉴分类名 F980 条目: {len(es)}\n")

    # 统计译文编码长度（含 0x00 结尾）
    lens = []
    samples = []
    for e in es:
        t = e.get("translated") or ""
        if not t:
            continue
        body = encode_body(cm, t)
        # 这个表用 0x00 结尾，把 FF 换成 00
        if body.endswith(b"\xFF"):
            body = body[:-1] + b"\x00"
        lens.append(len(body))
        if len(samples) < 8:
            samples.append((t, len(body)))

    if not lens:
        print("无译文")
        return 0

    lens.sort()
    print("=== 译文编码长度分布 ===")
    print(f"  条数 {len(lens)}")
    print(f"  最短 {lens[0]}B  中位 {lens[len(lens)//2]}B  最长 {lens[-1]}B")
    print()
    print("  样本:")
    for t, n in samples:
        print(f"    {t!r} = {n}B")

    # 各 stride 下塞得下的比例
    print()
    print("=== 不同 stride 下的塞得下比例 ===")
    print(f"  {'stride':>6} {'可用':>5} {'塞得下':>7} {'比例':>7}  倍数")
    for stride in (28, 56, 112):
        cap = stride          # name_offset=0
        # 减去元数据 22 字节（28-6=22）
        usable = stride - 22
        fit = sum(1 for n in lens if n <= usable)
        mult = stride // 28
        print(f"  {stride:>6} {usable:>5} {fit:>7} {fit/len(lens):>6.1%}  ×{mult}")

    print()
    print("=== 结论 ===")
    usable28 = 28 - 22
    fit28 = sum(1 for n in lens if n <= usable28)
    print(f"  保持 stride=28（可用 {usable28}B）: {fit28}/{len(lens)} 塞得下")
    if fit28 < len(lens):
        need = lens[-1]
        for stride in (56, 84, 112):
            usable = stride - 22
            if need <= usable:
                print(f"  ⇒ 需放大到 stride={stride}（可用 {usable}B，"
                      f"可容纳最长 {need}B）")
                print(f"     28 → {stride} 是 ×{stride // 28}，"
                      f"{'2的幂 ✅' if (stride & (stride-1)) == 0 else '非2幂 ⚠️'}")
                break
        print()
        print(f"  ⚠️ 注意：图鉴分类名表 straddle 386 项 × 28B = 10.8KB")
        print(f"     放大到 56 → 21.6KB，112 → 43.3KB（扩展区充足）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
