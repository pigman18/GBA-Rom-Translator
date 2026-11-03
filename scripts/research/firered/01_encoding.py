#!/usr/bin/env python3
"""调研① 火红汉化版用的编码协议是什么？

═══════════════════════════════════════════════════════════════════════════
【要回答的问题】（用户原话）
═══════════════════════════════════════════════════════════════════════════
「实际观察火红下来：貌似只用 f7，看看是否能借鉴过来，至少 f7、f9，
  能减少 1 位编码」

用户的意思是：火红汉化版可能只用了 **单字节 0xF7 起头的双字节编码**
（F7 XX），而我们的红宝石工程用的是 **F9 起头的双字节**
（F9 80 hi / F9 00 lead trail）。
如果火红真能用 2 字节表示一个汉字，而我们用 3 字节，那每字省 1 字节。

═══════════════════════════════════════════════════════════════════════════
【方法：统计各「前缀字节」的出现密度】
═══════════════════════════════════════════════════════════════════════════
GBA 文本在 ROM 里是连续字节流。汉化引入的编码前缀必然**高频重复**：
  · 如果是 2 字节编码 → 前缀字母（0xF7）出现次数 ≈ 汉字总数
  · 如果是 3 字节编码 → 前缀（0xF9）出现次数 ≈ 汉字总数

所以对原版与汉化版做**逐字节频率差**，就能看出汉化加了哪些前缀。

对比基线用**原版火红**（POKEMON_FIRE_BPRJ00.gba，同为日版），
这样差出来的高频字节只可能来自汉化。

用法：python scripts/research/firered/01_encoding.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

# 只统计文本段常见的字节范围（0x00-0xFF 全覆盖，但分开看高位）
HIGH = list(range(0xF0, 0x100))


def load(p: Path) -> bytes:
    if not p.is_file():
        raise SystemExit(f"[ERR] 找不到 {p}")
    return p.read_bytes()


def main() -> int:
    zh = load(FR_ZH)
    ja = load(FR_JA)
    print(f"汉化版 {FR_ZH.name}  {len(zh):,} B")
    print(f"原版   {FR_JA.name}  {len(ja):,} B")

    cz = Counter(zh)
    cj = Counter(ja)

    print("\n=== 0xF0–0xFF 各字节的出现次数（原版 vs 汉化）===")
    print(f"{'字节':>6} {'原版':>12} {'汉化':>12} {'倍数':>8}  ")
    rows = []
    for b in HIGH:
        a, c = cj.get(b, 0), cz.get(b, 0)
        ratio = (c / a) if a else float("inf") if c else 0.0
        rows.append((b, a, c, ratio))
    for b, a, c, r in rows:
        rs = f"{r:.2f}" if r not in (0, float("inf")) else ("∞" if r == float("inf") else "-")
        mark = "  ★ 显著增多" if r > 3 and c > 1000 else ""
        print(f"0x{b:02X}  {a:>12,} {c:>12,} {rs:>8}{mark}")

    print("\n=== 判读 ===")
    # 找出倍数最高的几个
    hot = [(b, a, c, r) for b, a, c, r in rows if c > 5000 and r > 2]
    hot.sort(key=lambda x: -x[3])
    if not hot:
        print("没有明显增多的前缀字节 ⇒ 可能汉化改了文本区以外的写法")
    for b, a, c, r in hot[:6]:
        print(f"  0x{b:02X} 从 {a:,} 涨到 {c:,}（{r:.1f} 倍）"
              f" ⇒ 疑似编码前缀")
    print("\n下一步：对这些候选前缀，抽一段文本看它后面跟几个字节，")
    print("      就能判断是 2 字节还是 3 字节编码。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
