#!/usr/bin/env python3
"""texts_28: 对照实验 —— 区分「收窄区间」与「filter 传法」各自的影响。

texts_27 发现：把剧情 start/end 收窄后丢 71 条，但丢失样本在 0x1D3xxx，
根本不在被切掉的区间内。说明丢失另有原因（filter 传法不同），
不能据此判断收窄的代价。

本脚本做三组对照，每组都只改一个变量：
  A 原样（不改 start/end，filters 传法同 texts_27）
  B 只改 start/end（同 A 的 filters 传法）
  C 原样 + 全局 filters 合并（模拟生产路径 resolve_filters）

A vs B 的差 = 收窄代价；A vs C 的差 = filter 传法差异。

用法: python scripts/research/ruby/texts_28_control.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def off_of(e) -> int:
    a = to_int(e.get("address")) or 0
    return a - 0x08000000 if a >= 0x08000000 else a


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    by_mod: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        by_mod[e.get("module")].append(e)
    cur = {off_of(e) for e in by_mod["剧情"]}

    base = dict(mods["剧情"])
    base["id"] = "剧情"

    def run(mod, label):
        out = TP.extract_module(rom, mod, "AXVJ", filters=mod.get("filters"))
        s = {off_of(e) for e in out}
        print(f"  {label:<46} {len(out):>6} 条")
        return s

    print("=" * 112)
    print("对照：剧情模块（filters 一律只传模块自身的，不合并全局）")
    print("=" * 112)
    A = run(dict(base), "A 原样 0x0..0xFFFFFF")
    B1 = dict(base); B1["start"] = "0x100000"; B1["end"] = "0x3F2000"
    B = run(B1, "B 收窄 0x100000..0x3F2000")
    B2 = dict(base); B2["start"] = "0x100000"; B2["end"] = "0xFFFFFF"
    Bx = run(B2, "B' 只收 start 0x100000..0xFFFFFF")

    print()
    print(f"  texts.json 现有条目: {len(cur)}")
    print(f"  A 与现有条目的差: 多 {len(A - cur)} / 少 {len(cur - A)}")
    print(f"  B 相对 A 丢失: {len(A - B)}   新增: {len(B - A)}")
    print(f"  B' 相对 A 丢失: {len(A - Bx)}  新增: {len(Bx - A)}")
    if A - B:
        print(f"  B 丢失样本: {[hex(x) for x in sorted(A - B)[:10]]}")
    if cur - A:
        lost = sorted(cur - A)
        print(f"  A 丢掉现有条目的样本: {[hex(x) for x in lost[:10]]}")
        from collections import Counter
        print(f"  这些地址的分箱: {Counter(x >> 16 for x in lost).most_common(6)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
