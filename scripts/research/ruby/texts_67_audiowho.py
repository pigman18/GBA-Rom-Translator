#!/usr/bin/env python3
"""texts_67: C 类音效标签 —— 用「所在的指针表是谁在用」判定，而不是只看指针形态。

texts_66 发现：战斗台词（确定上屏）和音效标签的指针**都在连续数组里**，
所以「连续数组」这个判据无区分度，作废。

换判据：看那些指针表**本身有没有被代码引用**，以及它们的位置属于哪片内存。

已知：
  音效标签的指针表在 0x3A5C9C / 0x3A649C / 0x3A652C 等（都在 0x3A5xxx-0x3A6xxx）
  战斗台词的指针表在 0x3DC2D0（在 0x3Dxxxx）

思路：0x3A5xxx 这片如果整体是「资源/数据区」而非「文本区」，就能判。
本脚本测这片区的性质：是不是紧邻 0x3A6483（道具名表）之后的资源区。

用法: python scripts/research/ruby/texts_67_audiowho.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000


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
    print("1) 0x3A5xxx 这片到底是什么 —— 把整片文本串列出来看语义")
    print("=" * 112)
    sys.path.insert(0, str(ROOT / "src"))
    from meowth.jp_pcs import decode_pcs

    segs = []
    start = 0x3A5700
    for i in range(0x3A5700, 0x3A6600):
        if rom[i] == 0xFF:
            t = decode_pcs(rom[start:i + 1])
            if t:
                segs.append((start, t))
            start = i + 1
    print(f"  0x3A5700..0x3A6600 共 {len(segs)} 段，前 40 段：")
    for off, t in segs[:40]:
        print(f"    0x{off:06X} {t!r}")

    print()
    print("=" * 112)
    print("2) 这些指针表有没有被代码引用")
    print("=" * 112)
    # 这些表的位置
    tables = [0x3A5C9C, 0x3A649C, 0x3A652C, 0x3A5E2C, 0xB575C, 0xB6424]
    for t in tables:
        target = BASE + t
        refs = []
        for o in range(0, len(rom) - 4, 4):
            if struct.unpack_from("<I", rom, o)[0] == target:
                refs.append(o)
        print(f"  表 0x{t:06X}: 被代码/数据引用的字面量 {len(refs)} 个 "
              f"{[hex(r) for r in refs[:4]]}")

    print()
    print("=" * 112)
    print("3) 对照：战斗台词指针表 0x3DC2D0 的引用情况")
    print("=" * 112)
    target = BASE + 0x3DC2D0
    refs = []
    for o in range(0, len(rom) - 4, 4):
        if struct.unpack_from("<I", rom, o)[0] == target:
            refs.append(o)
    print(f"  0x3DC2D0: {len(refs)} 个引用 {[hex(r) for r in refs[:6]]}")

    print()
    print("=" * 112)
    print("4) 判定")
    print("=" * 112)
    print("""
  关键区分点：
    · 0x3A5xxx 片的内容全是 2-4 字母的全角拉丁缩写（ＢＧＭ/ＳＥ/ＰＡＮ/ＢＯＯ/ＥＸＰ）
      且夹在 `しまった`/`みつけた` 这类短词之间 —— 疑似**调试/音效检查菜单的字面表**
    · 若是音效检查菜单（游戏里有 Sound Test 之类的开发者界面），
      它确实会**显示在屏幕上**，但不是玩家正常流程会看到的
    """)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
