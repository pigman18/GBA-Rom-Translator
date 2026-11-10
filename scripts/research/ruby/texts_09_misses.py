#!/usr/bin/env python3
"""texts_09: 找出定长表里「未被 lexicon 命中」的槽——定位表尾/表头多出的非名字槽。

对每个定长表：按模块声明的几何逐槽解码，标出
  - 命中 lexicon 的（真名字）
  - 未命中的（可能是：表尾填充/表头指针/非名字槽/别名）
并把未命中槽的 index、地址、解码文本列出来，用于判断 start/end 该收到哪。

用法: python scripts/research/ruby/texts_09_misses.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402

MODULE_LEX = {
    "招式名": "招式.json",
    "特性名": "特性.json",
    "道具名": "道具.json",
    "属性名": "属性.json",
    "宝可梦名": "图鉴.json",
}


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


def slot_text(rom: bytes, off: int, window: int, eos: int = 0xFF) -> str:
    limit = min(len(rom), off + window)
    for i in range(off, limit):
        if rom[i] == eos:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]

    for name, fn in MODULE_LEX.items():
        m = mods.get(name)
        if not m:
            continue
        keys = set(json.loads((LEX / fn).read_text(encoding="utf-8")).keys())
        r = m.get("read") or {}
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        stride = r.get("stride") or r.get("entry_size")
        eos = int(r.get("eos", 0xFF))
        no = int(r.get("name_offset") or 0)
        n = (end - start + 1) // stride

        misses = []
        for k in range(n):
            off = start + k * stride + no
            t = slot_text(rom, off, stride - no, eos)
            if t not in keys:
                misses.append((k, off, t, rom[off:off + stride].hex(" ")))

        print("=" * 112)
        print(f"{name}  lexicon={fn} start=0x{start:06X} stride={stride} n={n} "
              f"未命中={len(misses)}")
        print("=" * 112)
        for k, off, t, h in misses:
            print(f"  [{k:>3}] 0x{off:06X}  {h:<30} {t!r}")

        # 统计未命中是否集中在头/尾
        if misses:
            idxs = [k for k, _, _, _ in misses]
            head = sum(1 for k in idxs if k < n * 0.1)
            tail = sum(1 for k in idxs if k > n * 0.9)
            print(f"  -> 未命名槽分布：前 10% 有 {head} 个，后 10% 有 {tail} 个，"
                  f"中间 {len(idxs) - head - tail} 个")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
