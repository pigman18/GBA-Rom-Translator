#!/usr/bin/env python3
"""查 SLT2 表里宝可梦名对应的中文值，确认映射是否错乱。

SLT2 v2 布局：
  header: magic | n_buckets<<0 | max_jp_len<<16 | offsets[n+1]
  entry:  key(4B FNV1a) | jp_len_le16(2B) | jp_bytes | chinese_bytes(...0xFF)

若多个不同日文名对应同一个中文（如都是「蛋」），说明生成时数据错乱。

用法：
    python scripts/research/ruby/a2_dump_slt2.py
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
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000
SLOT = 0x01EA0000

TARGETS = ["ラグラージ", "ジュカイン", "サナギラス", "キノココ", "タマゴ"]


def main() -> int:
    import json
    rom = OUT.read_bytes()

    magic = struct.unpack_from("<I", rom, SLOT)[0]
    if magic != 0x32544C53:
        sys.exit("SLT2 magic 不对")
    hdr = struct.unpack_from("<I", rom, SLOT + 4)[0]
    n_bkt = hdr & 0xFFFF
    maxlen = (hdr >> 16) & 0xFFFF
    print(f"SLT2 @0x{SLOT:06X}  n_buckets={n_bkt}  max_jp_len={maxlen}")

    # 解析 offsets
    offs = struct.unpack_from(f"<{n_bkt + 1}I", rom, SLOT + 8)
    print(f"  桶偏移 {n_bkt + 1} 个，末值 {offs[-1]}")

    # 从 build.json 取目标日文原字节
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    jp_of = {}
    cn_of = {}
    for e in d.get("entries") or []:
        if e.get("module") != "宝可梦名":
            continue
        orig = e.get("original") or ""
        if orig not in TARGETS:
            continue
        try:
            jp = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        while jp and jp[-1] == 0xFF:
            jp = jp[:-1]
        jp_of[orig] = jp
        cn_of[orig] = e.get("translated")

    print(f"\n=== 目标宝可梦 ===")
    for name in TARGETS:
        jp = jp_of.get(name)
        cn = cn_of.get(name)
        if jp is None:
            print(f"  {name}: build.json 无此条")
            continue
        # 在 SLT2 里找 jp 字节序列，读它后面的中文
        pos = rom.find(jp, SLOT, 0x01EC0000)
        if pos < 0:
            print(f"  {name}: ❌ SLT2 里找不到")
            continue
        # jp 之后就是中文（到 0xFF）
        after = pos + len(jp)
        end = rom.find(b"\xFF", after, after + 32)
        cn_bytes = rom[after:end] if end >= 0 else rom[after:after + 16]
        print(f"  {name}  jp@{pos:#x}")
        print(f"    build.json 译文: {cn!r}")
        print(f"    SLT2 里存的中文: {cn_bytes.hex(' ')}")
        # 解出中文码位
        codes = []
        i = 0
        while i + 3 <= len(cn_bytes):
            if cn_bytes[i] == 0xF9 and cn_bytes[i + 1] == 0x00:
                codes.append((cn_bytes[i + 2] << 8) | cn_bytes[i + 3])
                i += 4
            else:
                i += 1
        print(f"    码位: {[hex(c) for c in codes]}")

    # 统计：SLT2 里所有宝可梦名条目的中文是否有大量重复
    print()
    print("=== SLT2 宝可梦名段的中文重复检查 ===")
    from collections import Counter
    cnt = Counter()
    hit = 0
    for name, jp in jp_of.items():
        pos = rom.find(jp, SLOT, 0x01EC0000)
        if pos < 0:
            continue
        after = pos + len(jp)
        end = rom.find(b"\xFF", after, after + 32)
        if end < 0:
            continue
        cnt[rom[after:end]] += 1
        hit += 1
    print(f"  找到 {hit}/{len(jp_of)} 条")
    for b, c in cnt.most_common(6):
        print(f"    {b.hex(' ')} × {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
