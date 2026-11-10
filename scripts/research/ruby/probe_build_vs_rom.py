#!/usr/bin/env python3
"""核对 build.json 里的 original_hex 与 ROM 实际字节是否一致。

目的：上一支脚本发现符号表 gMoveNames=0x081C8DC8（354×13=4615B）
      与模块配置 招式名 start=0x1CAD04 stride=8 不一致。
      先确认「配置的地址确实是 ROM 里那段文本」，否则后续 relocate 判断全错。

判据：entries 的 original_hex 逐字节等于 ROM[address]。
      一致率高 → 配置几何正确（符号名只是别名/UNVERIFIED）
      一致率低 → 配置地址错了

用法：
    python scripts/research/ruby/probe_build_vs_rom.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

POINTER_OFFSET = 0x08000000

CHECK_MODULES = [
    "招式名", "道具名", "图鉴分类名", "秘密基地装饰名",
    "属性名", "特性名", "树果名", "性格名",
]


def main() -> int:
    rom = ROM.read_bytes()
    data = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    print(f"ROM {len(rom):,} B / entries {len(entries):,}\n")

    rows = []
    for mod in CHECK_MODULES:
        es = [e for e in entries if e.get("module") == mod]
        if not es:
            print(f"[skip] {mod}: 无条目")
            continue
        ok = bad = empty = 0
        bad_samples = []
        for e in es:
            try:
                addr = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
            except ValueError:
                bad += 1
                continue
            if addr >= POINTER_OFFSET:
                addr -= POINTER_OFFSET
            try:
                orig = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                empty += 1
                continue
            if not orig:
                empty += 1
                continue
            if addr + len(orig) > len(rom):
                bad += 1
                continue
            if rom[addr:addr + len(orig)] == orig:
                ok += 1
            else:
                bad += 1
                if len(bad_samples) < 3:
                    bad_samples.append(
                        (e.get("address"), orig.hex(" "), rom[addr:addr + len(orig)].hex(" "))
                    )

        total = ok + bad
        rate = ok / total if total else 0.0
        verdict = "OK  几何正确" if rate >= 0.95 else ("MISMATCH" if rate < 0.5 else "PARTIAL")
        rows.append({"module": mod, "entries": len(es), "ok": ok, "bad": bad,
                     "empty": empty, "rate": rate, "verdict": verdict})

        print(f"=== {mod} ===  条目 {len(es)}")
        print(f"  原文与 ROM 一致 {ok}/{total} ({rate:.1%})  空 {empty}")
        print(f"  ⇒ {verdict}")
        for a, o, r in bad_samples:
            print(f"      {a}: build={o[:60]}")
            print(f"      {' '*len(str(a))}  rom  ={r[:60]}")
        print()

    out = ROOT / "work" / "_probe" / "ruby_build_vs_rom.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
