#!/usr/bin/env python3
"""调研(102) 找字形指针表 —— 有 2000+ 字形就一定有索引表。

═══════════════════════════════════════════════════════════════════════════
【逻辑链】
═══════════════════════════════════════════════════════════════════════════
 1. 码位是 `F7 hi lo`（hi 密集在 0x00–0x0A，lo 铺满 0–255）
    ⇒ 码位空间约 11 × 256 = 2816
 2. VRAM 只装当前帧的 ~47 个字（(101) 实测）
    ⇒ 字形必须从别处按需加载
 3. 按需加载必然有**索引结构**：码位 → 字形数据地址

【去哪找】
 这张表一定在汉化新增区（原版全 FF 的区域）。
 (96) 列出过候选：0x08908000 / 0x089B0000 / 0x08A70000 / 0x08B00000 …

 判据：一张「码位索引表」应该满足：
   · 连续多个 u32（或 u16）指向同一片区域
   · 目标地址递增（字形按码位顺序排）
   · 表项数 ≥ 2000

【本脚本】
 ① 在汉化新增区里扫「连续 u32 指向同一区且递增」的数组
 ② 也扫 u16 形式
 ③ 对找到的数组，读它指向的数据，判断是不是 1bpp/2bpp/4bpp 字形

用法：python scripts/research/firered/102_font_index.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 扫「连续 u32 指向 ROM 且递增」的数组（≥500 项）")
    print("=" * 78)
    m = n // 4 * 4
    pv = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pv >= BASE) & (pv < BASE + n)

    runs = []
    i = 0
    while i < len(pv):
        if is_rom[i]:
            j = i
            while j + 1 < len(pv) and is_rom[j + 1]:
                j += 1
            cnt = j - i + 1
            if cnt >= 500:
                vals = pv[i:j + 1].astype(np.int64)
                # 递增比例
                inc = int((np.diff(vals) > 0).sum())
                runs.append((cnt, i * 4, int(vals[0]) - BASE,
                             int(vals[-1]) - BASE, inc / max(1, cnt - 1)))
            i = j + 1
        else:
            i += 1

    runs.sort(key=lambda r: -r[0])
    print(f"  找到 {len(runs)} 个 ≥500 项的连续 ROM 指针数组")
    print(f"  {'表位置':>14} {'项数':>6} {'首目标':>12} {'末目标':>12} "
          f"{'递增率':>7} {'原版此槽'}")
    for cnt, off, t0, t1, incr in runs[:15]:
        old = struct.unpack_from("<I", ja, off)[0]
        print(f"  0x{BASE+off:08X} {cnt:>6} 0x{BASE+t0:08X} 0x{BASE+t1:08X} "
              f"{incr:>6.1%} 0x{old:08X}")

    # ── ② 对最像索引表的，验证目标数据 ──────────────────────────
    print("\n" + "=" * 78)
    print("② 检查候选表的表项间隔（字形字节数）")
    print("=" * 78)
    for cnt, off, t0, t1, incr in runs[:6]:
        if incr < 0.8:
            continue
        vals = pv[off // 4:(off // 4) + min(cnt, 300)].astype(np.int64) - BASE
        gaps = np.diff(vals)
        from collections import Counter
        gc = Counter(gaps.tolist())
        print(f"\n  表 0x{BASE+off:08X}（{cnt} 项，递增 {incr:.0%}）")
        print(f"    目标间隔 top6：{gc.most_common(6)}")
        print(f"    前 8 个目标：{[f'0x{BASE+int(v):08X}' for v in vals[:8]]}")
        # 若间隔恒定，那就是固定尺寸字形
        if gc:
            g0, c0 = gc.most_common(1)[0]
            print(f"    ⇒ 最常见间隔 {g0} 字节（占 {c0/max(1,len(gaps)):.0%}）")

    # ── ③ 也扫 u16 形式 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 扫 u16 索引表（值在 0..0xFFFF，且大量递增）")
    print("=" * 78)
    p16 = np.frombuffer(zh[:m], dtype="<u2")
    best = []
    for off in range(0, len(p16) - 2048, 2):
        seg = p16[off:off + 2048].astype(np.int32)
        inc = int((np.diff(seg) > 0).sum())
        if inc > 1800 and seg.max() < 60000:
            best.append((inc, off * 2, int(seg[0]), int(seg[-1])))
    best.sort(reverse=True)
    print(f"  候选 {len(best)} 个")
    for inc, off, v0, v1 in best[:10]:
        old = struct.unpack_from("<H", ja, off)[0]
        print(f"  0x{BASE+off:08X} 递增 {inc}/2047  值 {v0}..{v1}  "
              f"原版此槽 0x{old:04X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
