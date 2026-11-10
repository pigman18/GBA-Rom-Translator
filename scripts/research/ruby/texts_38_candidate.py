#!/usr/bin/env python3
"""texts_38: 第4步候选配置生成器 —— 在可信模拟器上做「改前/改后」对照。

改动只涉及 3 个全 ROM scan 模块的 start/end（不碰 filters），
并用 texts_37 的全流程模拟器验证条目集合差异。

已实测的硬事实：
  · scan 模块只搜 start..end，收窄到覆盖全部条目即可
  · 但生产路径有 FCFS，必须整体模拟才能判断归属

用法:
    python scripts/research/ruby/texts_38_candidate.py            # 生成候选并对照
    python scripts/research/ruby/texts_38_candidate.py --apply    # 应用候选
"""
from __future__ import annotations

import argparse
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
CAND = ROOT / "work" / "_candidate_texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research" / "ruby"))
from texts_37_simulate import simulate, key_of  # noqa: E402


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    data = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = data["modules"]

    print("=" * 112)
    print("基线模拟（当前配置）")
    print("=" * 112)
    base = simulate(rom, mods, cfg={"texts": {}})
    for mid, els in base.items():
        print(f"  {mid:<18} {len(els):>5}")
    print(f"  {'合计':<18} {sum(len(v) for v in base.values()):>5}")

    # 各 scan 模块的真实范围（用基线模拟结果，而不是文件）
    print()
    print("=" * 112)
    print("scan 模块在基线中的真实条目范围")
    print("=" * 112)
    spans = {}
    for n in ("UI界面", "剧情", "补漏剧情"):
        offs = sorted(to_int(e.get("address")) - 0x08000000
                      for e in base.get(n, []))
        if not offs:
            print(f"  {n:<10} 无条目")
            continue
        spans[n] = (offs[0], offs[-1])
        print(f"  {n:<10} n={len(offs):>5}  0x{offs[0]:06X}..0x{offs[-1]:06X}")

    # 构造候选：区间收窄到「真实范围 + 0x1000 余量」，对齐到 4KB
    cand_mods = json.loads(json.dumps(mods))
    print()
    print("=" * 112)
    print("候选改动：收窄 start/end（不改 filters）")
    print("=" * 112)
    for n, (lo, hi) in spans.items():
        ns = max(0, (lo - 0x1000) & ~0xFFF)
        ne = min(0x7FFFFF, ((hi + 0x1000) | 0xFFF))
        old = (cand_mods[n].get("start"), cand_mods[n].get("end"))
        cand_mods[n]["start"] = f"0x{ns:X}"
        cand_mods[n]["end"] = f"0x{ne:X}"
        print(f"  {n:<10} {old[0]}..{old[1]}  ->  0x{ns:X}..0x{ne:X}")

    print()
    print("=" * 112)
    print("候选模拟 + 对照")
    print("=" * 112)
    new = simulate(rom, cand_mods, cfg={"texts": {}})
    same = True
    for mid in cand_mods:
        o = {key_of(x) for x in base.get(mid, [])}
        n = {key_of(x) for x in new.get(mid, [])}
        if o != n:
            same = False
            print(f"  ⚠️ {mid:<18} 基线 {len(o):>5} 候选 {len(n):>5} "
                  f"仅基线 {len(o - n):>4} 仅候选 {len(n - o):>4}")
    to = sum(len(v) for v in base.values())
    tn = sum(len(v) for v in new.values())
    print(f"  合计 基线 {to} -> 候选 {tn}")

    all_o = set().union(*[{key_of(x) for x in v} for v in base.values()])
    all_n = set().union(*[{key_of(x) for x in v} for v in new.values()])
    print(f"  全局丢失 {len(all_o - all_n)}  新增 {len(all_n - all_o)}")
    if all_o - all_n:
        for k in sorted(all_o - all_n)[:10]:
            print(f"      丢 {k}")

    data["modules"] = cand_mods
    CAND.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\n-> 候选已写 {CAND}")

    if a.apply and same:
        TEXTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        print(f"[ok] 已应用到 {TEXTS}")
    elif a.apply:
        print("[!] 有差异，未应用")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
