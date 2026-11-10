#!/usr/bin/env python3
"""调研(164) 离线分析快照：在 EWRAM 里找字形，再反查 ROM。

═══════════════════════════════════════════════════════════════════════════
【已拿到完整快照（163）】
═══════════════════════════════════════════════════════════════════════════
work/_probe/snap3/
    ewram.bin      262,144 B  非零 37,843
    iwram.bin       32,768 B  非零 10,528
    vram.bin        98,304 B  非零 10,763
    palette/oam/io
    menu.png       （中文菜单，已肉眼确认）

⇒ **之后不再启模拟器，全部离线分析。**

【分析思路】
 已知 E1: DMA 把 EWRAM 的缓冲送进 VRAM（(152) R3=0x020047F0 等）
 已知 E2: VRAM 里字形 nibble 10/11/12（palette15 映射后）
 已知 E3: 汉字 11×11、步进 13

 ① 在 EWRAM 里找所有「nibble 集中在 1/2/3」的 32B 块
    （若 EWRAM 是原始值，字形应是 1/2/3；若已映射则是 10/11/12）
 ② 把找到的块拿去 ROM 里搜
 ③ 命中的位置就是字库源

用法：python scripts/research/firered/164_offline_ewram_font.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    ew = (SNAP / "ewram.bin").read_bytes()
    vr = (SNAP / "vram.bin").read_bytes()
    iw = (SNAP / "iwram.bin").read_bytes()

    print("=" * 78)
    print("① 三块内存的 nibble 分布对比（判断字形用哪套值）")
    print("=" * 78)
    for name, blob in (("EWRAM", ew), ("IWRAM", iw), ("VRAM", vr)):
        arr = np.frombuffer(blob, dtype=np.uint8)
        hi = arr >> 4
        lo = arr & 0x0F
        c = Counter()
        for v in range(16):
            n = int(((hi == v) | (lo == v)).sum())
            if n:
                c[v] = n
        tot = sum(c.values())
        top = " ".join(f"{k}:{v*100//tot}" for k, v in sorted(c.items()))
        print(f"  {name:<6} nibble%: {top}")

    # ── ② 在 EWRAM 找字形块（两种判据都试）──────────────
    print("\n" + "=" * 78)
    print("② EWRAM 里找「字形块」（32B，nibble 集中在少数值）")
    print("=" * 78)
    for label, allowed in (("原始 1/2/3", {0, 1, 2, 3}),
                           ("映射 10/11/12", {0, 10, 11, 12})):
        hits = []
        for off in range(0, len(ew) - 32, 32):
            blob = ew[off:off + 32]
            u = set(v for b in blob for v in (b & 0xF, b >> 4))
            if not u <= allowed:
                continue
            # 必须有墨（不是全空）
            ink = sum(1 for b in blob for v in (b & 0xF, b >> 4) if v)
            if ink < 6:
                continue
            hits.append((off, ink))
        print(f"  {label}: {len(hits)} 个块")
        if hits:
            # 聚成连续段
            runs = []
            s = p = hits[0][0]
            for o, _ in hits[1:]:
                if o == p + 32:
                    p = o
                else:
                    runs.append((s, p + 32))
                    s = p = o
            runs.append((s, p + 32))
            runs.sort(key=lambda r: -(r[1] - r[0]))
            print(f"    聚成 {len(runs)} 段，前 8 大：")
            for a, b in runs[:8]:
                print(f"      0x{0x02000000+a:08X}..0x{0x02000000+b:08X}"
                      f"  {(b-a)//32} 块")

    # ── ③ 用 EWRAM 里的字形块去 ROM 搜 ──────────────────
    print("\n" + "=" * 78)
    print("③ 拿 EWRAM 字形块去 ROM 搜")
    print("=" * 78)
    cand = []
    for off in range(0, len(ew) - 32, 32):
        blob = ew[off:off + 32]
        u = set(v for b in blob for v in (b & 0xF, b >> 4))
        if u <= {0, 1, 2, 3}:
            ink = sum(1 for b in blob for v in (b & 0xF, b >> 4) if v)
            if ink >= 8:
                cand.append((off, blob))
    print(f"  候选块 {len(cand)}")

    hits = []
    for off, blob in cand:
        i = zh.find(blob)
        if i >= 0:
            hits.append((off, i, blob))
    print(f"  在 ROM 命中 {len(hits)} / {len(cand)}")
    for eoff, roff, blob in hits[:10]:
        isnew = "★汉化新增" if ja[roff:roff + 32] != blob else "原版相同"
        print(f"    EWRAM 0x{0x02000000+eoff:08X} → ROM 0x{BASE+roff:08X} "
              f"{isnew}")

    if hits:
        from collections import Counter as C2
        zones = C2(h[1] // 0x10000 for h in hits)
        print(f"\n  命中按 64KB 分布：")
        for k, v in zones.most_common(10):
            print(f"    0x{BASE+k*0x10000:08X}: {v}")

    # ── ④ 也试「映射值 10/11/12」的块 ───────────────────
    print("\n" + "=" * 78)
    print("④ 映射值（10/11/12）的 EWRAM 块去 ROM 搜")
    print("=" * 78)
    cand2 = []
    for off in range(0, len(ew) - 32, 32):
        blob = ew[off:off + 32]
        u = set(v for b in blob for v in (b & 0xF, b >> 4))
        if u <= {0, 10, 11, 12} and (11 in u or 12 in u):
            cand2.append((off, blob))
    print(f"  候选 {len(cand2)}")
    hits2 = []
    for off, blob in cand2:
        i = zh.find(blob)
        if i >= 0:
            hits2.append((off, i))
    print(f"  命中 {len(hits2)}")
    for eoff, roff in hits2[:8]:
        print(f"    EWRAM 0x{0x02000000+eoff:08X} → ROM 0x{BASE+roff:08X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
