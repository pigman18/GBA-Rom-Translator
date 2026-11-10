#!/usr/bin/env python3
"""验证通用流水线：6 张定长表走 READ → CLASSIFY → PLACE → RELINK。

6 张表的几何（全部用「100% 合规」判据实测，见 A26_REDO.md）：
  招式名        base=0x1CACFC stride=8  usable=8  eos=0xFF n=354  最长21B → stride 32
  特性名        base=0x1CBC44 stride=8  usable=8  eos=0xFF n=77   最长17B → stride 32
  属性名        base=0x1CBB0C stride=5  usable=5  eos=0xFF n=18   最长13B → stride 20
  道具名        base=0x39A648 stride=40 usable=9  eos=0xFF n=348  最长29B → stride 80
  图鉴分类名    base=0x38474C stride=28 usable=6  eos=0x00 n=386  最长17B → stride 56
  秘密基地装饰名 base=0x3C2A44 stride=28 usable=10 eos=0xFF n=120  最长29B → stride 56

用法：
    python scripts/research/ruby/a2_pipeline_verify.py
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

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OUT = ROOT / "work" / "_probe" / "a2_pipeline_result.json"

TABLES = {
    "招式名":         {"base": 0x1CACFC, "stride": 8,  "usable": 8,
                       "n": 354, "eos": 0xFF},
    "特性名":         {"base": 0x1CBC44, "stride": 8,  "usable": 8,
                       "n": 77,  "eos": 0xFF},
    "属性名":         {"base": 0x1CBB0C, "stride": 5,  "usable": 5,
                       "n": 18,  "eos": 0xFF},
    "道具名":         {"base": 0x39A648, "stride": 40, "usable": 9,
                       "n": 348, "eos": 0xFF},
    "图鉴分类名":     {"base": 0x38474C, "stride": 28, "usable": 6,
                       "n": 386, "eos": 0x00},
    "秘密基地装饰名": {"base": 0x3C2A44, "stride": 28, "usable": 10,
                       "n": 120, "eos": 0xFF, "name_offset": 1},
}


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.text_pipeline import run_pipeline
    from meowth.region_alloc import default_allocator

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    entries = [e for e in (d.get("entries") or [])
               if e.get("type") == "replace"
               and e.get("phrase_code") is not None
               and (e.get("module") or "") in TABLES]

    print(f"待处理条目 {len(entries):,}（6 张表）\n")
    print("跑流水线：READ → CLASSIFY → PLACE → RELINK …\n")

    def encoder(text: str) -> bytes:
        b = cm.encode(text)
        if not b.endswith(b"\xFF"):
            b = bytes(b) + b"\xFF"
        return bytes(b)

    alloc = default_allocator()
    result = run_pipeline(
        rom=rom, entries=entries, tables=TABLES,
        encoder=encoder, alloc=alloc, only_tables=True,
    )

    # 结果
    print("=== 表处理结果 ===")
    print(f"{'表':<16} {'条目':>5} {'旧stride':>9} {'新stride':>9} "
          f"{'模式':<10} {'新体积':>9} {'字面量':>7}")
    print("-" * 82)
    for t in result.tables:
        print(f"{t.name:<16} {t.n_entries:>5} {t.orig_stride:>9} "
              f"{t.new_stride:>9} {t.mode:<10} {t.size:>9,} {len(t.literals):>7}")

    print()
    print("=== 汇总 ===")
    s = result.summary
    print(f"  处理条目   {s['total']:,}")
    print(f"  定长表     {s['tables']}")
    print(f"  字节 patch {s['byte_patches']:,} 处")
    print(f"  新区已用   {s['alloc_used']:,} B")
    print(f"  新区剩余   {s['alloc_remaining']:,} B")

    # 校验：每条都被正确放置
    print()
    print("=== 校验 ===")
    bad = [e for e in result.entries if e.placed_offset == 0]
    print(f"  未放置的条目: {len(bad)}"
          + ("  ✅" if not bad else f"  ❌ {bad[0].entry_id}"))

    # 校验：新表字节里每项含 eos
    print()
    print("=== 新表字节校验 ===")
    for tname, (base, blob) in result.table_blobs.items():
        geom = TABLES[tname]
        stride = t.new_stride if (t := next(x for x in result.tables
                                            if x.name == tname)) else geom["stride"]
        ok = 0
        for i in range(geom["n"]):
            seg = blob[i * stride:(i + 1) * stride]
            if seg and geom["eos"] in seg:
                ok += 1
        print(f"  {tname:<16} {ok}/{geom['n']} 项含 eos 0x{geom['eos']:02X}"
              + ("  ✅" if ok == geom["n"] else "  ⚠️"))

    # 保存
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "tables": [
            {"name": t.name, "orig_base": f"0x{t.orig_base:06X}",
             "new_base": f"0x{t.new_base:06X}", "orig_stride": t.orig_stride,
             "new_stride": t.new_stride, "mode": t.mode, "size": t.size,
             "n_entries": t.n_entries, "literals": len(t.literals)}
            for t in result.tables
        ],
        "summary": result.summary,
        "sample_entries": [
            {"id": e.entry_id, "module": e.module,
             "old": f"0x{e.old_offset:06X}",
             "placed": f"0x{e.placed_offset:06X}",
             "mode": e.placed_mode, "note": e.note}
            for e in result.entries[:8]
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
