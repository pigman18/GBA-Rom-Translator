#!/usr/bin/env python3
"""texts_51: 用「FF 分隔」重新切 0x3B2 词库（不是 PCS 串长读）。

texts_50 的错：read_pcs 遇到非法字节会继续拼，把长段吞成 1 条超长串
（实测有一条 700+ 字节的串），导致 1199 条里 10% 命中率 —— 那是把数据区当文本。

正确做法（Chief 的描述）：**按 FF 分隔切**，每个 FF 之间算一段，
再判断这段是不是干净的假名词条。这也是「按自然词结尾扫」的含义。

用法: python scripts/research/ruby/texts_51_ffsplit.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"
BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs, BYTE_TO_CHAR  # noqa: E402


def load_vocab() -> set[str]:
    v = set()
    for p in LEX.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                v.update(k for k in d if isinstance(k, str))
        except Exception:
            pass
    return v


def clean_kana(s: str) -> bool:
    """是否像「干净词条」：全部由假名/汉字假名/全角字母数字构成，无乱码符号。"""
    if not s or len(s) > 24:
        return False
    ok = 0
    for ch in s:
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF:      # 假名
            ok += 1
        elif ch in "ー・‥．×／":
            ok += 1
        elif 0xFF10 <= o <= 0xFF5A:    # 全角数字字母
            ok += 1
        elif 0x4E00 <= o <= 0x9FFF:    # 汉字
            ok += 1
        else:
            return False
    return ok == len(s)


def main() -> int:
    rom = ROM_PATH.read_bytes()
    vocab = load_vocab()
    print(f"词表 {len(vocab):,}")

    LO, HI = 0x3B219B, 0x3B6600
    print()
    print("=" * 112)
    print(f"按 FF 分隔切 {hex(LO)}..{hex(HI)}")
    print("=" * 112)

    segs = []
    start = LO
    i = LO
    while i < HI:
        if rom[i] == 0xFF:
            raw = rom[start:i + 1]
            t = decode_pcs(raw)
            if t:
                segs.append((start, raw, t))
            start = i + 1
        i += 1

    print(f"  切成 {len(segs)} 段")
    clean = [(o, r, t) for o, r, t in segs if clean_kana(t)]
    print(f"  其中「干净假名词条」: {len(clean)}")
    hit = sum(1 for _, _, t in clean if t in vocab)
    print(f"  干净词条中词表命中: {hit}/{len(clean)} ({hit/max(len(clean),1):.1%})")

    print()
    print("  前 15 条干净词条：")
    for o, _, t in clean[:15]:
        print(f"      0x{o:06X} {t!r}")
    print("  ...")
    print("  后 10 条干净词条：")
    for o, _, t in clean[-10:]:
        print(f"      0x{o:06X} {t!r}")

    print()
    print("=" * 112)
    print("干净词条的地址跨度与分布")
    print("=" * 112)
    if clean:
        print(f"  0x{clean[0][0]:06X} .. 0x{clean[-1][0]:06X}")
        # 找断点
        gaps = []
        for k in range(1, len(clean)):
            d = clean[k][0] - clean[k - 1][0]
            if d > 0x60:
                gaps.append((clean[k - 1][0], clean[k][0], d))
        print(f"  大间隔（>0x60）{len(gaps)} 处：")
        for a, b, d in gaps[:10]:
            print(f"      0x{a:06X} -> 0x{b:06X}  （间隔 0x{d:X}）")

    print()
    print("=" * 112)
    print("这些干净词条有指针吗")
    print("=" * 112)
    targets: set[int] = set()
    for o in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + len(rom):
            targets.add(v - BASE)
    with_ptr = [o for o, _, _ in clean if o in targets]
    print(f"  {len(with_ptr)}/{len(clean)} 有 u32 指针")
    if with_ptr:
        print(f"  样本: {[hex(x) for x in with_ptr[:8]]}")

    print()
    print("=" * 112)
    print("与词表分类对照（这些词属于哪些表）")
    print("=" * 112)
    cats = {}
    for name, fn in (("招式", "招式.json"), ("特性", "特性.json"), ("道具", "道具.json"),
                     ("属性", "属性.json"), ("性格", "性格.json"), ("图鉴", "图鉴.json"),
                     ("地点", "地点.json"), ("短语", "短语.json"), ("UI", "UI.json")):
        p = LEX / fn
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                cats[name] = set(d.keys())
        except Exception:
            pass
    from collections import Counter
    c = Counter()
    for _, _, t in clean:
        for name, ks in cats.items():
            if t in ks:
                c[name] += 1
                break
        else:
            c["未命中任何表"] += 1
    for k, v in c.most_common():
        print(f"    {k:<16} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
