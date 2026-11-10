#!/usr/bin/env python3
"""texts_06: 用项目自带抽取器重跑每个模块，与 texts.json 现存条目逐条 diff。

这是最硬的证据链：
  - 抽取器 (src/util/texts_patcher.py) 是产出 texts.json 的同一个代码路径
  - 用同一份 ROM + 同一份 module 定义重跑 → 结果应当 == texts.json
  - 不相等的地方，就是 texts.json 已经和 ROM/定义脱节之处（陈旧/手工改过/错几何）

用法: python scripts/research/ruby/texts_06_reextract.py [--module 名字]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
OUTDIR = ROOT / "work" / "_probe"

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module")
    a = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    entries = d["entries"]

    by_mod: dict[str, list] = {}
    for e in entries:
        by_mod.setdefault(e.get("module"), []).append(e)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    print(f"{'module':<22} {'type':<11} {'cfg_n':>6} {'re_n':>6} {'only_cfg':>9} "
          f"{'only_re':>8} {'text_diff':>10}")
    print("-" * 84)

    report = {}
    for name, m in mods.items():
        if a.module and name != a.module:
            continue
        mod = dict(m)
        mod["id"] = name
        try:
            new = TP.extract_module(rom, mod, "AXVJ", filters=None)
        except Exception as exc:  # noqa: BLE001
            print(f"{name:<22} 抽取异常: {exc}")
            report[name] = {"error": str(exc)}
            continue
        old = by_mod.get(name, [])
        old_map = {(e.get("address"), (e.get("original_hex") or "")) for e in old}
        new_map = {(e.get("address"), (e.get("original_hex") or "")) for e in new}
        only_old = old_map - new_map
        only_new = new_map - old_map
        # 同地址不同文本
        old_by_addr = {}
        for e in old:
            old_by_addr.setdefault(e.get("address"), []).append(e.get("original"))
        new_by_addr = {}
        for e in new:
            new_by_addr.setdefault(e.get("address"), []).append(e.get("original"))
        text_diff = 0
        for addr in set(old_by_addr) & set(new_by_addr):
            if sorted(map(str, old_by_addr[addr])) != sorted(map(str, new_by_addr[addr])):
                text_diff += 1

        report[name] = {
            "type": m.get("type"),
            "cfg_n": len(old),
            "re_n": len(new),
            "only_cfg": len(only_old),
            "only_re": len(only_new),
            "text_diff": text_diff,
            "sample_only_cfg": [(x[0], x[1][:40]) for x in list(only_old)[:5]],
            "sample_only_re": [(x[0], x[1][:40]) for x in list(only_new)[:5]],
        }
        print(f"{name:<22} {str(m.get('type')):<11} {len(old):>6} {len(new):>6} "
              f"{len(only_old):>9} {len(only_new):>8} {text_diff:>10}")

    (OUTDIR / "texts_reextract.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUTDIR / 'texts_reextract.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
