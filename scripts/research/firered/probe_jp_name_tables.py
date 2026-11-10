#!/usr/bin/env python3
"""精确定位火红原版 gMoveNames / gItemNames：用真实日文名字节定位。

上一支脚本用「每 stride 末位是 FF」找表，被大片 FF 填充误报。
改用确定锚点：火红日文字符集（pokeemerald/firered charmap）：

  0x00 空格
  0xA1-0xAA 数字 0-9
  0xBB-0xD4 A-Z
  0xD5-0xEE a-z
  0xFF 终止

  假名（firered 日版）：
    ぁ 0x01 あ 0x02 ぃ 0x03 い 0x04 ぅ 0x05 う 0x06 ...
  先不猜假名码，直接用「已知假名单词的出现情况」反推：
  在 ROM 里搜「相同字节序列重复出现 354 次、间隔 13」的模式。

更稳的做法：火红招式名表紧跟物种名表。已知 FIRERED_FULL_LOGIC 提到
原版日文文本区在 0x083DDxxx。直接从那里找 FF 结尾的密集串。

本脚本：
  1. 扫 0x300000..0x400000（原版日文文本区）找 FF 结尾串
  2. 统计「长 11/12/13 且内容为假名区字节」的串密度
  3. 定位后对比汉化版同地址

用法：
    python scripts/research/firered/probe_jp_name_tables.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"


def is_kana(b: int) -> bool:
    # 日版假名区大致 0x01..0x60；排除 0x00 空格与 >=0xB0 的拉丁
    return 0x01 <= b <= 0x60


def scan_kana_runs(rom: bytes, lo: int, hi: int):
    """扫 FF 结尾串，返回 (偏移, 长度, 假名占比) 列表。"""
    out = []
    i = lo
    while i < hi:
        if rom[i] == 0xFF:
            i += 1
            continue
        j = i
        while j < hi and rom[j] != 0xFF and rom[j] != 0xFE:
            j += 1
        if j < hi and rom[j] == 0xFF and 2 <= (j - i) <= 20:
            seg = rom[i:j]
            kana = sum(1 for b in seg if is_kana(b))
            out.append((i, j - i, kana / len(seg)))
        i = j + 1 if j > i else i + 1
    return out


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()
    print(f"origin/zh 都是 {len(a):,} B\n")

    for lo, hi in ((0x300000, 0x400000), (0x400000, 0x500000)):
        runs = scan_kana_runs(a, lo, hi)
        kana_runs = [r for r in runs if r[2] > 0.9]
        print(f"=== 原版 0x{lo:06X}..0x{hi:06X} ===")
        print(f"  FF 结尾串 {len(runs):,}，其中假名纯度>90% 的 {len(kana_runs):,}")
        if not kana_runs:
            continue

        # 找密度最高的连续区：按 4KB 桶聚合
        buckets: dict[int, int] = {}
        for off, _l, _p in kana_runs:
            buckets[off >> 12] = buckets.get(off >> 12, 0) + 1
        top = sorted(buckets.items(), key=lambda kv: -kv[1])[:6]
        print("  假名串最密的 4KB 桶:")
        for seg, cnt in top:
            base = seg << 12
            print(f"    0x{base:06X}  {cnt} 串")
            # 看这一段在两版是否一致
            d = sum(1 for x, y in zip(a[base:base+0x1000], b[base:base+0x1000]) if x != y)
            print(f"      前 4KB 差异 {d}/4096 ({d/4096:.0%})")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
