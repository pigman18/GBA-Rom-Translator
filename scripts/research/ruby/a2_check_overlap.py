#!/usr/bin/env python3
"""排查：我的新表是否覆盖了 SLT2 表或字库。

已确认 build.json 里宝可梦名译文正确（巨沼怪/蜥蜴王/蘑蘑菇），
但运行时不显示，说明是 SLT2 查表时映射错了。

怀疑：新表 0x09EB0000 起，而 SLT2 表在 0x09EA0000，
      6 张表共 70,274 B → 到 0x09EC1282。
      SlotTable 只占 0x09EA0000..0x09EB0000（64KB），**不冲突**。

但 tiles 那步说「new_palette=0x09EC1284（ignore yaml 0x09200000）」，
这个 0x09EC1284 正好在新表末尾 0x09EC1282 之后 2 字节！可能撞上。

需要验证：
  1. 新表区间 vs SlotTable 区间
  2. 新表区间 vs tiles 新调色板位置
  3. SLT2 表内容是否完整

用法：
    python scripts/research/ruby/a2_check_overlap.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
GBA_BASE = 0x08000000

# 新表区间（文件偏移）
NEW_TABLES = [
    ("属性名",         0x01EB0000, 306),
    ("特性名",         0x01EB0134, 2464),
    ("秘密基地装饰名", 0x01EB3714, 6720),
    ("道具名",         0x01EB5154, 27840),
    ("招式名",         0x01EB0AD4, 11328),
    ("图鉴分类名",     0x01EBBE14, 21616),
]

# 已知占用
KNOWN = [
    ("SlotTable",      0x01EA0000, 0x01EB0000, "SLT2 查表"),
    ("TilesPalette",   0x01EC1284, 0x01EC1384, "tiles 新调色板"),
]


def main() -> int:
    rom = OUT.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    # 汇总新表总区间
    lo = min(t[1] for t in NEW_TABLES)
    hi = max(t[1] + t[2] for t in NEW_TABLES)
    print("=== 新表区间 ===")
    for name, start, size in NEW_TABLES:
        print(f"  {name:<16} 0x{start:06X}..0x{start + size:06X}  {size:>7,}B")
    print(f"  合计区间 0x{lo:06X}..0x{hi:06X}")

    print()
    print("=== 已知占用 ===")
    for name, s, e, note in KNOWN:
        conflict = not (hi <= s or lo >= e)
        mark = "❌ 重叠！" if conflict else "✅ 不冲突"
        print(f"  {name:<16} 0x{s:06X}..0x{e:06X}  {note}  {mark}")

    # 逐对检查
    print()
    print("=== 逐对检查 ===")
    for tname, ts, tsz in NEW_TABLES:
        te = ts + tsz
        for kname, ks, ke, _ in KNOWN:
            if not (te <= ks or ts >= ke):
                print(f"  ❌ {tname}(0x{ts:06X}..0x{te:06X}) 撞 "
                      f"{kname}(0x{ks:06X}..0x{ke:06X})")

    # 验证 SlotTable 完整性
    print()
    print("=== SlotTable 完整性 ===")
    slot_off = 0x01EA0000
    magic = struct.unpack_from("<I", rom, slot_off)[0]
    print(f"  magic @0x{slot_off:06X} = 0x{magic:08X}"
          + ("  ✅ 'SLT2'" if magic == 0x32544C53 else "  ❌ 不是 SLT2"))
    if magic == 0x32544C53:
        hdr = struct.unpack_from("<I", rom, slot_off + 4)[0]
        n_bkt = hdr & 0xFFFF
        maxlen = (hdr >> 16) & 0xFFFF
        print(f"  n_buckets={n_bkt}  max_jp_len={maxlen}")

    # 检查 SLT2 表里是否有宝可梦名的映射
    print()
    print("=== SLT2 表里查宝可梦名 ===")
    # ラグラージ = 8b 44 2e 6f 5c 7e a1 a9? 需从 build.json 拿 original_hex
    import json
    build = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
    d = json.loads(build.read_text(encoding="utf-8"))
    targets = {"ラグラージ", "ジュカイン", "サナギラス", "キノココ"}
    for e in d.get("entries") or []:
        if e.get("module") != "宝可梦名":
            continue
        orig = e.get("original") or ""
        if orig not in targets:
            continue
        try:
            jp = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        while jp and jp[-1] == 0xFF:
            jp = jp[:-1]
        # 在 SLT2 表区域里搜原始日文字节
        found_at = rom.find(jp, slot_off, 0x01EC0000)
        mark = f"找到 @0x{found_at:06X}" if found_at >= 0 else "❌ 未找到"
        print(f"  {orig} (jp={jp.hex(' ')}) → {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
