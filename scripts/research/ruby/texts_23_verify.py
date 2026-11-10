#!/usr/bin/env python3
"""texts_23: 验证 texts.json 改动后的正确性（第 1、2 步的验收）。

检查：
  V1 JSON 可解析、模块数/条目数自洽
  V2 6 张基准表按新定义抽取，条数与首末条与 ground truth 一致
  V3 两处几何修正生效（树果 43、性格 25）
  V4 条目与模块几何不再脱节（逐模块重抽 diff）
  V5 被移出的 7 条能力页串确实不在 性格名 里，且已存档

用法: python scripts/research/ruby/texts_23_verify.py
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
BACKUP = ROOT / "work" / "_texts_backup_before_d.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402

# ground truth：(start, end, stride, 槽位数, 有效条目数)
# 道具名 348 槽里 67 个是「？？？？？？？？」占位，filter 跳过后有效 281 条。
GT = {
    "招式名":         (0x1CAD04, 0x1CB813, 8,   354, 354),
    "特性名":         (0x1CBC4C, 0x1CBEB3, 8,    77,  77),
    "属性名":         (0x1CBB0C, 0x1CBB65, 5,    18,  18),
    "道具名":         (0x39A648, 0x39DCA7, 40,  348, 281),
    "图鉴分类名":     (0x384746, 0x38717D, 28,  386, 386),
    "秘密基地装饰名": (0x3C2A54, 0x3C3773, 28,  120, 120),
    "树果名":         (0x3A1050, 0x3A1503, 28,   43,  43),
    "性格名":         (0x3971E8, 0x39724C, 4,    25,  25),
}


def run(mod_in: dict, name: str, rom: bytes) -> list[dict]:
    """按生产路径抽取：非 scan 模块用其自带的 filters 列表。"""
    mod = dict(mod_in)
    mod["id"] = name
    return TP.extract_module(rom, mod, "AXVJ", filters=mod.get("filters") or None)


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    entries = d["entries"]

    print("=" * 104)
    print("V1 结构自洽")
    print("=" * 104)
    print(f"  modules = {len(mods)}")
    print(f"  count    = {d.get('count')}")
    print(f"  entries  = {len(entries)}")
    print(f"  count == len(entries): {d.get('count') == len(entries)}")
    by_mod = defaultdict(list)
    for e in entries:
        by_mod[e.get("module")].append(e)
    missing = [n for n in mods if n not in by_mod]
    print(f"  无条目的模块: {missing if missing else '（无）'}")

    print()
    print("=" * 104)
    print("V2/V3 基准表几何与条数")
    print("=" * 104)
    print(f"  {'module':<18} {'start':>12} {'end':>12} {'stride':>7} {'槽位':>6} "
          f"{'有效n':>6} {'GT槽':>5} {'GT有效':>6}  结果")
    print("  " + "-" * 100)
    ok_all = True
    for name, (gs, ge, gst, gslots, gvalid) in GT.items():
        m = mods.get(name)
        if not m:
            print(f"  {name:<18} 模块不存在 ❌")
            ok_all = False
            continue
        s = int(m["start"], 16)
        e = int(m["end"], 16)
        r = m.get("read") or {}
        st = r.get("stride") or r.get("entry_size")
        slots = (e - s + 1) // st
        out = run(m, name, rom)
        good = (s == gs and e == ge and st == gst and slots == gslots
                and len(out) == gvalid)
        if not good:
            ok_all = False
        print(f"  {name:<18} 0x{s:08X} 0x{e:08X} {st:>7} {slots:>6} "
              f"{len(out):>6} {gslots:>5} {gvalid:>6}  {'✅' if good else '❌'}")

    print()
    print("=" * 104)
    print("V4 全模块：几何 vs 条目是否脱节（重抽 diff）")
    print("=" * 104)
    drift = []
    for name, m in mods.items():
        if m.get("type") == "scan":
            continue
        try:
            out = run(m, name, rom)
        except Exception as exc:  # noqa: BLE001
            drift.append((name, f"异常 {exc}"))
            continue
        old = by_mod.get(name, [])
        o = {(x.get("address"), x.get("original_hex")) for x in old}
        n = {(x.get("address"), x.get("original_hex")) for x in out}
        if o != n:
            drift.append((name, f"旧 {len(old)} 新 {len(out)}，仅旧 {len(o - n)}，仅新 {len(n - o)}"))
    if drift:
        for name, why in drift:
            print(f"  ⚠️ {name:<18} {why}")
    else:
        print("  ✅ 所有非 scan 模块的条目与几何精确一致（0 脱离）")

    print()
    print("=" * 104)
    print("V5 移出的 7 条能力页串")
    print("=" * 104)
    reserved = json.loads((ROOT / "work" / "_reserved_ui_detail.json").read_text(encoding="utf-8"))
    nat_addrs = {e.get("address") for e in by_mod.get("性格名", [])}
    still = [r["address"] for r in reserved if r["address"] in nat_addrs]
    print(f"  存档 {len(reserved)} 条，仍在 性格名 里的: {still if still else '无 ✅'}")
    print(f"  性格名 现存 {len(by_mod.get('性格名', []))} 条")

    print()
    print("=" * 104)
    print("V6 与备份对比：只有预期模块变化")
    print("=" * 104)
    if BACKUP.exists():
        old = json.loads(BACKUP.read_text(encoding="utf-8"))
        om = old["modules"]
        for name in mods:
            if json.dumps(om.get(name), sort_keys=True) != json.dumps(mods[name], sort_keys=True):
                print(f"  模块定义变化: {name}")
        ob = defaultdict(int)
        for e in old["entries"]:
            ob[e.get("module")] += 1
        nb = defaultdict(int)
        for e in entries:
            nb[e.get("module")] += 1
        for name in sorted(set(ob) | set(nb)):
            if ob[name] != nb[name]:
                print(f"  条目数变化: {name:<16} {ob[name]} -> {nb[name]}")

    print()
    print("=" * 104)
    print("结论:", "全部通过 ✅" if ok_all else "有未通过项 ❌")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
