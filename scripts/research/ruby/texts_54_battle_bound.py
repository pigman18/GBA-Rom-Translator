#!/usr/bin/env python3
"""texts_54: 战斗提示 0x3DA000 那段起点是否正确（同法复核，避免重犯）。

用 texts_53 同样的「形态干净 + 词表命中」判据，在 0x3D0000..0x3DC000 找真实起点。
若 0x3DA000 之前就已经有干净文本，说明区间起点偏后；
若 0x3DA000 之前是数据，说明起点正确。

用法: python scripts/research/ruby/texts_54_battle_bound.py
"""
from __future__ import annotations

import json
import re
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

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402

KANA = re.compile(r"^[\u3040-\u30ff\uFF10-\uFF5A\u4E00-\u9FFFー・‥．×！？。、]+$")


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
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))

    print("=" * 112)
    print("0x3D0000..0x3DC000 每个 0x400 桶的文本密度")
    print("=" * 112)
    for base in range(0x3D0000, 0x3DC000, 0x400):
        segs = []
        start = base
        for i in range(base, min(base + 0x400, len(rom))):
            if rom[i] == 0xFF:
                t = decode_pcs(rom[start:i + 1])
                if t and KANA.match(t) and 2 <= len(t) <= 40:
                    segs.append((start, t))
                start = i + 1
        bar = "#" * min(len(segs), 50)
        print(f"  0x{base:06X}  {len(segs):>3}  {bar}")

    print()
    print("=" * 112)
    print("文件里 0x3DA000..0x3DC000 的条目样本（证明这段确实是战斗提示）")
    print("=" * 112)
    z = [e for e in d["entries"]
         if 0x3DA000 <= to_int(e["address"]) - 0x08000000 < 0x3DC000]
    print(f"  共 {len(z)} 条")
    for e in z[:12]:
        print(f"    {e['address']} [{e['module']}] {e['original'][:46]!r}")

    print()
    print("=" * 112)
    print("对照：0x3D C000..0x3E0000（相邻区段）密度，看边界是否合理")
    print("=" * 112)
    for base in range(0x3DC000, 0x3E0000, 0x800):
        segs = []
        start = base
        for i in range(base, min(base + 0x800, len(rom))):
            if rom[i] == 0xFF:
                t = decode_pcs(rom[start:i + 1])
                if t and KANA.match(t) and 2 <= len(t) <= 40:
                    segs.append((start, t))
                start = i + 1
        print(f"  0x{base:06X}  {len(segs):>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
