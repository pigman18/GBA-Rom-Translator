#!/usr/bin/env python3
"""texts_37: 全流程模拟器 —— 复刻 export_texts 的 FCFS 归属，做「改前改后」对照。

texts_36 失败的原因：单模块独立重抽不等于生产行为。
生产路径（export_texts）是：
  1. 按 modules 声明顺序逐个抽取
  2. 每个模块抽完后，把它占用的字节带加入 exported_bands
  3. 后续模块抽取时排除这些已占用的带（exclude_ranges）
  4. 最后按 address 去重（seen_addr），并把落在 claimed_by 的条目标记为 shadowed_by

本脚本完整复刻 1-4，然后对比「当前 texts.json」与「候选新 texts.json」的最终条目集合。

用法:
    python scripts/research/ruby/texts_37_simulate.py            # 只跑当前配置，作为基线
    python scripts/research/ruby/texts_37_simulate.py --cand     # 跑候选配置并对比
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


def simulate(rom: bytes, mods: dict, verbose: bool = False,
             cfg: dict | None = None) -> dict[str, list[dict]]:
    """复刻 export_texts 的主循环。

    与生产路径对齐的关键点：
      - ptr_index：scan 模块需要它识别「有指针的文本」
      - resolve_filters：全局 texts.filters + 模块 filters 按 id 合并
      - exclude_ranges：FCFS 已导出带
    """
    # 生产路径会构建 ptr_index（scan 模块必需）
    need_ptr = any(str(m.get("type") or "scan") in ("scan", "addr_bands")
                   for m in mods.values())
    ptr_index = TP._build_ptr_index(rom) if need_ptr else None
    if verbose:
        print(f"    ptr_index: {len(ptr_index) if ptr_index else 0} 个目标")

    exported_bands: list[tuple[int, int]] = []
    seen_addr: set[str] = set()
    result: dict[str, list[dict]] = {}

    for mid, mod in mods.items():
        m = dict(mod)
        m["id"] = mid
        # 与 export_texts 一致：用 resolve_filters 合并全局+模块 filters
        try:
            flt = TP.resolve_filters(cfg or {"texts": {}}, m)
        except Exception:
            flt = m.get("filters")
        try:
            chunk = TP.extract_module(
                rom, m, "AXVJ",
                ptr_index=ptr_index,
                filters=flt,
                exclude_ranges=exported_bands,
            )
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"    [{mid}] 抽取异常: {exc}")
            result[mid] = []
            continue
        kept = []
        for e in chunk:
            addr = e.get("address")
            if addr and addr in seen_addr:
                continue
            if addr:
                seen_addr.add(addr)
                bl = e.get("byte_length") or 0
                if bl > 0:
                    a = to_int(addr) or 0
                    lo = a - 0x08000000 if a >= 0x08000000 else a
                    exported_bands.append((lo, lo + bl))
            kept.append(e)
        result[mid] = kept
        if verbose:
            print(f"    [{mid}] type={m.get('type')!r} -> {len(kept)} 条")
    return result


def key_of(e) -> tuple:
    return (e.get("address"), e.get("original_hex"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", action="store_true",
                    help="同时跑 work/_candidate_texts.json 并对比")
    a = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    cur_data = json.loads(TEXTS.read_text(encoding="utf-8"))
    cur = simulate(rom, cur_data["modules"])

    print("=" * 112)
    print("基线：当前 texts.json 全流程模拟")
    print("=" * 112)
    tot = 0
    for mid, els in cur.items():
        tot += len(els)
        print(f"  {mid:<18} {len(els):>5}")
    print(f"  {'合计':<18} {tot:>5}")

    # 与文件里的实际条目比对，确认模拟器可信
    file_by_mod: dict[str, list] = defaultdict(list)
    for e in cur_data["entries"]:
        file_by_mod[e.get("module")].append(e)
    print()
    print("模拟器 vs 文件实际条目（验证模拟器可信度）")
    drift = 0
    for mid, els in cur.items():
        f = {key_of(x) for x in file_by_mod.get(mid, [])}
        s = {key_of(x) for x in els}
        if f != s:
            drift += 1
            print(f"  ⚠️ {mid:<18} 文件 {len(f):>5} 模拟 {len(s):>5} "
                  f"仅文件 {len(f - s):>3} 仅模拟 {len(s - f):>3}")
    if drift == 0:
        print("  ✅ 逐模块与文件完全一致 —— 模拟器可信")

    if a.cand:
        cand_p = ROOT / "work" / "_candidate_texts.json"
        if not cand_p.exists():
            print(f"\n[!] 候选文件不存在: {cand_p}")
            return 1
        cd = json.loads(cand_p.read_text(encoding="utf-8"))
        new = simulate(rom, cd["modules"])
        print()
        print("=" * 112)
        print("候选配置 vs 基线：条目差异")
        print("=" * 112)
        for mid in cd["modules"]:
            o = {key_of(x) for x in cur.get(mid, [])}
            n = {key_of(x) for x in new.get(mid, [])}
            if o != n:
                print(f"  {mid:<18} 基线 {len(o):>5} 候选 {len(n):>5} "
                      f"仅基线 {len(o - n):>4} 仅候选 {len(n - o):>4}")
        to = sum(len(v) for v in cur.values())
        tn = sum(len(v) for v in new.values())
        print(f"  {'合计':<18} 基线 {to:>5} 候选 {tn:>5}")
        # 全局：是否有条目被整体丢掉
        all_o = set().union(*[{key_of(x) for x in v} for v in cur.values()])
        all_n = set().union(*[{key_of(x) for x in v} for v in new.values()])
        print(f"\n  全局丢失 {len(all_o - all_n)}，全局新增 {len(all_n - all_o)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
