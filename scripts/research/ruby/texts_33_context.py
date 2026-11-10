#!/usr/bin/env python3
"""texts_33: fallback 71 条 —— 用「ROM 邻域结构」判真伪（最客观，不靠语言启发式）。

前四版判据都失败过：
  texts_29 假名占比        → 误杀战斗提示
  texts_30 裸F7/F8         → 漏掉纯假名乱码
  texts_31 片段命中率      → 伪乱码被单字片段刷高
  texts_32 长片段词表覆盖  → 战斗提示经控制码剥离后片段太少，又被误杀

本版换思路：**看这条文本在 ROM 里的邻域结构**。
  真实文本池的特征：前后邻接的是别的文本串（都是 FF 结尾的串），
                    即文本以「串链」形式成片存在。
  二进制数据伪命中的特征：起止点外围是任意字节（非文本串边界），
                    或者紧邻 LZ 压缩头 / 指针数组 / 图形调色板。

判据：
  N1 起点前 1 字节是 0xFF（说明我们是从另一条串的结尾切进来的 → 像串链）
  N2 起点前 2-8 字节内能找到一个 0xFF（同上）
  N3 终止 FF 之后紧跟的字节是否像另一条串的开头（字形字节）
三条都不满足 → 孤立的、周围是二进制的伪命中。

用法: python scripts/research/ruby/texts_33_context.py
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
OUT = ROOT / "work" / "_probe" / "texts_context_verdict.json"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR  # noqa: E402


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


def glyph_like(b: int) -> bool:
    """该字节像不像一个字形（可用于判断是否串链的一部分）。"""
    return b in BYTE_TO_CHAR or b in (0xFE, 0xFA, 0xFB, 0xFC, 0xFD, 0xFF)


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    fb = [e for e in d["entries"]
          if e.get("module") == "剧情" and "fallback" in e]

    print("=" * 116)
    print("按 ROM 邻域结构判定（N1/N2/N3）")
    print("=" * 116)

    rows = []
    for e in fb:
        a = to_int(e.get("address")) or 0
        off = a - 0x08000000 if a >= 0x08000000 else a
        ln = e.get("byte_length") or 0
        prev1 = rom[off - 1] if off > 0 else 0
        # 前 8 字节内有没有 FF
        prev_ff = any(rom[k] == 0xFF for k in range(max(0, off - 8), off))
        end = off + ln
        nxt = rom[end] if end < len(rom) else 0xFF
        n1 = prev1 == 0xFF
        n2 = prev_ff
        n3 = glyph_like(nxt) and nxt != 0xFF or (nxt == 0xFF)
        chain = n1 or n2
        rows.append((e, off, n1, n2, n3, chain, prev1, nxt))

    iso = [r for r in rows if not r[5]]
    chained = [r for r in rows if r[5]]
    print(f"\n  处于串链中（前后有 FF 边界）: {len(chained)}")
    print(f"  孤立（周围非文本边界）      : {len(iso)}")

    print()
    print("=" * 116)
    print("A. 孤立条目（伪命中嫌疑最大）")
    print("=" * 116)
    for e, off, n1, n2, n3, chain, p1, nx in iso:
        print(f"  0x{off:06X} prev=0x{p1:02X} next=0x{nx:02X}  "
              f"{(e.get('original') or '')[:48]!r}")

    print()
    print("=" * 116)
    print("B. 串链内条目抽样（多为正常）")
    print("=" * 116)
    for e, off, n1, n2, n3, chain, p1, nx in chained[:12]:
        print(f"  0x{off:06X} prev=0x{p1:02X}  "
              f"{(e.get('original') or '')[:48]!r}")

    OUT.write_text(json.dumps(
        {"isolated": [{"address": e.get("address"), "original": e.get("original")}
                      for e, *_ in iso],
         "chained_count": len(chained)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
