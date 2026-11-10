#!/usr/bin/env python3
"""最终验证：6 张表 + 定稿 stride，跑通用流水线。

定稿几何（对应 patches/table_stride.asm）：
  招式名          base=0x1CACFC stride 8→32  usable 8→32  eos=0xFF n=354
  特性名          base=0x1CBC44 stride 8→32  usable 8→32  eos=0xFF n=77
  属性名          base=0x1CBB0C stride 5→17  usable 5→17  eos=0xFF n=18
  道具名          base=0x39A648 stride 40→80 usable 9→49  eos=0xFF n=348
  图鉴分类名      base=0x38474C stride 28→56 usable 6→34  eos=0x00 n=386
  秘密基地装饰名  base=0x3C2A44 stride 28→56 usable 10→38 eos=0xFF n=120 name_offset=1

用法：
    python scripts/research/ruby/a2_pipeline_final.py
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
OUT = ROOT / "work" / "_probe" / "a2_final_result.json"

# 定稿：new_stride / new_usable 由 asm patch 决定
TABLES = {
    "招式名":         {"base": 0x1CACFC, "stride": 8,  "usable": 8,
                       "new_stride": 32, "new_usable": 32,
                       "n": 354, "eos": 0xFF, "name_offset": 0},
    "特性名":         {"base": 0x1CBC44, "stride": 8,  "usable": 8,
                       "new_stride": 32, "new_usable": 32,
                       "n": 77,  "eos": 0xFF, "name_offset": 0},
    "属性名":         {"base": 0x1CBB0C, "stride": 5,  "usable": 5,
                       "new_stride": 17, "new_usable": 17,
                       "n": 18,  "eos": 0xFF, "name_offset": 0},
    "道具名":         {"base": 0x39A648, "stride": 40, "usable": 9,
                       "new_stride": 80, "new_usable": 49,
                       "n": 348, "eos": 0xFF, "name_offset": 0},
    "图鉴分类名":     {"base": 0x38474C, "stride": 28, "usable": 6,
                       "new_stride": 56, "new_usable": 34,
                       "n": 386, "eos": 0x00, "name_offset": 0},
    "秘密基地装饰名": {"base": 0x3C2A44, "stride": 28, "usable": 10,
                       "new_stride": 56, "new_usable": 38,
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

    print(f"待处理 {len(entries):,} 条（6 张表）\n")

    def encoder(text: str) -> bytes:
        b = cm.encode(text)
        return bytes(b) if b.endswith(b"\xFF") else bytes(b) + b"\xFF"

    alloc = default_allocator()
    result = run_pipeline(
        rom=rom, entries=entries, tables=TABLES,
        encoder=encoder, alloc=alloc, only_tables=True,
    )

    print("=== 表处理结果 ===")
    print(f"{'表':<16} {'条目':>5} {'stride':>10} {'可用':>6} "
          f"{'新体积':>9} {'字面量':>6}")
    print("-" * 66)
    for t in result.tables:
        g = TABLES[t.name]
        print(f"{t.name:<16} {t.n_entries:>5} "
              f"{t.orig_stride}→{t.new_stride:<6} "
              f"{g['new_usable']:>6} {t.size:>9,} {len(t.literals):>6}")

    print()
    print("=== 汇总 ===")
    s = result.summary
    print(f"  条目       {s['total']:,}")
    print(f"  字节 patch {s['byte_patches']:,} 处")
    print(f"  新区已用   {s['alloc_used']:,} B")
    print(f"  新区剩余   {s['alloc_remaining']:,} B")

    print()
    print("=== 校验 ===")
    unplaced = [e for e in result.entries if e.placed_offset == 0]
    print(f"  未放置条目: {len(unplaced)}"
          + ("  ✅" if not unplaced else f"  ❌ {unplaced[0].entry_id}"))

    # 每项含 eos
    all_ok = True
    for tname, (base, blob) in result.table_blobs.items():
        g = TABLES[tname]
        stride = g["new_stride"]
        noff = g["name_offset"]
        usable = g["new_usable"]
        ok = 0
        for i in range(g["n"]):
            seg = blob[i * stride + noff:i * stride + noff + usable]
            if seg and g["eos"] in seg:
                ok += 1
        status = "✅" if ok == g["n"] else "⚠️"
        if ok != g["n"]:
            all_ok = False
        print(f"  {tname:<16} {ok}/{g['n']} 项含 eos  {status}")

    # 译文超长检查
    print()
    print("=== 译文是否超新可用宽度 ===")
    over = 0
    for e in result.entries:
        g = TABLES.get(e.module)
        if not g:
            continue
        if len(e.encoded) > g["new_usable"]:
            over += 1
            if over <= 5:
                print(f"  ⚠️ {e.module} {e.text!r} = {len(e.encoded)}B "
                      f"> {g['new_usable']}B")
    print(f"  超长: {over} 条" + ("  ✅" if over == 0 else ""))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "tables": [
            {"name": t.name, "orig_base": f"0x{t.orig_base:06X}",
             "new_base": f"0x{t.new_base:06X}",
             "orig_stride": t.orig_stride, "new_stride": t.new_stride,
             "new_usable": TABLES[t.name]["new_usable"],
             "size": t.size, "n_entries": t.n_entries,
             "literals": len(t.literals)}
            for t in result.tables
        ],
        "summary": s,
        "checks": {
            "unplaced": len(unplaced),
            "eos_ok": all_ok,
            "overflow": over,
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0 if (not unplaced and all_ok and over == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
