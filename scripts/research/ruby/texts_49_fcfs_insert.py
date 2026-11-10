#!/usr/bin/env python3
"""texts_49: 验证 Chief 的 3.3 思路 —— 新模块插在剧情之前，FCFS 能否自动认领。

Chief 的假设：FCFS 按模块顺序认领，新模块排在剧情前面就能先抢到 0x3B2 那批准入，
不需要改剧情的 filter。

本脚本用「原地序 vs 插队序」两种排列跑全流程模拟，对比 0x3B2 区段的归属。

关键：这是**全流程**模拟（含 FCFS），不是单模块重抽。
用法: python scripts/research/ruby/texts_49_fcfs_insert.py
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


def run_fcfs(rom, mods, ptr_index):
    """全流程 FCFS：按序抽取 + exported_bands 排除。"""
    bands: list[tuple[int, int]] = []
    seen: set[str] = set()
    out: dict[str, list] = {}
    for mid, mod in mods.items():
        m = dict(mod)
        m["id"] = mid
        flt = TP.resolve_filters({"texts": {}}, m)
        try:
            chunk = TP.extract_module(rom, m, "AXVJ", ptr_index=ptr_index,
                                      filters=flt, exclude_ranges=bands)
        except Exception:  # noqa: BLE001
            out[mid] = []
            continue
        kept = []
        for e in chunk:
            a = e.get("address")
            if a and a in seen:
                continue
            if a:
                seen.add(a)
                bl = e.get("byte_length") or 0
                if bl:
                    off = to_int(a) - 0x08000000
                    bands.append((off, off + bl))
            kept.append(e)
        out[mid] = kept
    return out


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    ptr_index = TP._build_ptr_index(rom)
    base_mods = d["modules"]

    LO, HI = 0x3B2000, 0x3B2A00

    print("=" * 108)
    print("A. 原地序（现状）：0x3B2 区段归属")
    print("=" * 108)
    a = run_fcfs(rom, base_mods, ptr_index)
    for mid, els in a.items():
        z = [e for e in els if LO <= to_int(e["address"]) - 0x08000000 < HI]
        if z:
            print(f"  {mid:<12} {len(z)} 条")

    print()
    print("=" * 108)
    print("B. 新模块插在 剧情 之前：FCFS 是否自动认领")
    print("=" * 108)

    # 新模块：scan 圈该段，用剧情同款 fallback 通道（因为该段多数无指针）
    story = dict(base_mods["剧情"])
    new_mod = {
        "id": "词库-0x3B2",
        "type": "scan",
        "start": f"0x{LO:X}",
        "end": f"0x{HI - 1:X}",
        "fallback_filters": story.get("fallback_filters") or [],
    }

    # 构造新顺序：新模块插到 剧情 之前
    order = list(base_mods.keys())
    idx = order.index("剧情")
    new_order = order[:idx] + ["词库-0x3B2"] + order[idx:]
    new_mods = {}
    for k in new_order:
        new_mods[k] = new_mod if k == "词库-0x3B2" else base_mods[k]

    print(f"  插入位置: 索引 {idx}（剧情 原在此位置）")
    print(f"  新模块定义: type=scan start=0x{LO:X} end=0x{HI-1:X} "
          f"fallback={[f.get('id') for f in new_mod['fallback_filters']]}")

    b = run_fcfs(rom, new_mods, ptr_index)
    total_a = sum(len(v) for v in a.values())
    total_b = sum(len(v) for v in b.values())
    print(f"\n  总条目: 原地 {total_a} -> 插入后 {total_b}  (Δ={total_b - total_a:+d})")
    for mid, els in b.items():
        z = [e for e in els if LO <= to_int(e["address"]) - 0x08000000 < HI]
        if z:
            print(f"  {mid:<12} {len(z)} 条")

    print()
    print("=" * 108)
    print("C. 结论")
    print("=" * 108)
    za = {to_int(e["address"]) for els in a.values() for e in els
          if LO <= to_int(e["address"]) - 0x08000000 < HI}
    zb = {to_int(e["address"]) for els in b.values() for e in els
          if LO <= to_int(e["address"]) - 0x08000000 < HI}
    print(f"  原地覆盖该段 {len(za)} 个地址；插入后 {len(zb)} 个")
    print(f"  插入后新增 {len(zb - za)}，丢失 {len(za - zb)}")
    if len(zb - za):
        print(f"    新增样本: {sorted(zb - za)[:6]}")
    if len(za - zb):
        print(f"    丢失样本: {sorted(za - zb)[:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
