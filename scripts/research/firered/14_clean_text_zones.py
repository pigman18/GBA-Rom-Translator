#!/usr/bin/env python3
"""调研⑭ 关键修正：低地址的「F7」是 Thumb 指令，不是文本。

═══════════════════════════════════════════════════════════════════════════
【上一轮的关键发现】
═══════════════════════════════════════════════════════════════════════════
抽样 0x08080000 区（代码段）：
    01 20 10 BC 02 BC 08 47 D0 50 00 03 D1 06 08 08 10 B5 00 06 ...
抽样 0x080A0000 区：
    60 F7 1A FD 50 20 E1 21 60 F7 16 FD 52 20 00 21 60 F7 12 FD ...

`60 F7` 是 **Thumb 指令 `b.n`（条件跳转）**：
    0xF760 = b.n，偏移量由后一字节决定
    比如 `60 F7 1A FD` = `b.n -0x2F0` 附近

⇒ 我在早期统计「全 ROM 的 F7」时，**把大量 Thumb 指令当成了文本编码前缀**，
   这就是得到 11,735 / 8,255 个假码位的根因。

═══════════════════════════════════════════════════════════════════════════
【本轮要给出「干净的 F7 文本区列表」】
═══════════════════════════════════════════════════════════════════════════
判据：一个 F7 算「文本前缀」需要满足
  1. 所在位置**不是代码段**（通过「前后字节是否符合 Thumb 对齐特征」排除）
  2. 前后是文本字节流（0x00-0x5A、0xA1-0xFF，且 0xFF 作分隔）

更实用的做法：**只看差异区**（原版≠汉化），代码段基本不改
（低地址区差异只有 0.2%）。

用法：python scripts/research/firered/14_clean_text_zones.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BLK = 0x1000


def is_textish(b: int) -> bool:
    return (b <= 0x5A) or (0xA1 <= b <= 0xFF)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja)) // BLK

    # 1) 只保留「与原版不同」且「F7 密度高」的块
    zones = []
    for i in range(n):
        a = ja[i * BLK:(i + 1) * BLK]
        b = zh[i * BLK:(i + 1) * BLK]
        if a == b:
            continue
        f7 = b.count(0xF7)
        if f7 < 32:          # 密度门槛：4KB 里至少 32 个 F7
            continue
        ff = b.count(0xFF)
        zones.append((i, f7, ff))

    zones.sort(key=lambda x: -x[1])
    print(f"=== F7 文本区（差异块 + F7 密度 ≥32）===")
    print(f"共 {len(zones)} 个 4KB 块，合计 F7 {sum(z[1] for z in zones):,} 个")
    print(f"\n{'ROM 地址':>12} {'F7':>6} {'FF':>6} {'FF占比'}")
    for i, f7, ff in zones[:20]:
        print(f"0x{0x08000000+i*BLK:08X} {f7:>6} {ff:>6} {ff/BLK*100:>5.1f}%")
    if len(zones) > 20:
        print(f"… 另有 {len(zones)-20} 块")

    # 2) 聚合成连续区间
    idxs = sorted(z[0] for z in zones)
    runs = []
    if idxs:
        s = p = idxs[0]
        for x in idxs[1:]:
            if x == p + 1:
                p = x
            else:
                runs.append((s, p))
                s = p = x
        runs.append((s, p))
    runs.sort(key=lambda r: -(r[1] - r[0]))
    print(f"\n=== 聚合为 {len(runs)} 个连续区间（前 10）===")
    for s, e in runs[:10]:
        nb = e - s + 1
        f7 = sum(z[1] for z in zones if s <= z[0] <= e)
        print(f"  ROM 0x{0x08000000+s*BLK:08X}..0x{0x08000000+(e+1)*BLK:08X}"
              f"  {nb*BLK//1024}KB  F7 {f7:,}")

    # 3) 在这些干净区里重新统计码位
    print("\n=== 在干净文本区重新统计码位 ===")
    pairs = Counter()
    for i, _, _ in zones:
        seg = zh[i * BLK:(i + 1) * BLK]
        j = seg.find(b"\xf7")
        while j >= 0 and j + 2 < len(seg):
            pairs[(seg[j + 1], seg[j + 2])] += 1
            j = seg.find(b"\xf7", j + 1)

    print(f"  不同码位：**{len(pairs):,}**")
    his = sorted({h for h, l in pairs})
    print(f"  hi 用到 {len(his)} 种：0x{min(his):02X} – 0x{max(his):02X}")
    freq = sorted(pairs.values(), reverse=True)
    tot = sum(freq)
    for k in (500, 1000, 2000, 3000, 4096):
        if k <= len(freq):
            print(f"    前 {k:>4} 高频字覆盖 {sum(freq[:k])/tot*100:>5.1f}%")

    print(f"\n=== 结论 ===")
    print(f"  干净统计下真实码位 {len(pairs):,}")
    print("  这个数字才是「火红字库需要多少个字」的可靠答案。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
