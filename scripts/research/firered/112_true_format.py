#!/usr/bin/env python3
"""调研(112) 定案：字库格式 = 每字形 64 字节（32 字节头 + 32 字节字形）。

═══════════════════════════════════════════════════════════════════════════
【(111) 发现的真实结构】
═══════════════════════════════════════════════════════════════════════════
 0x08FE4560: 00 00 00 00 00 00 00 00 | 66 66 66 66 | 77 77 77 77 | 33 33 33 33
             | 22 21 21 22 11 11 11 21 22 21 21 22 …（32 字节字形）
 0x08FE45A0: 00 00 00 00 00 00 00 00 | 66 66 66 66 | 77 77 77 77 | 33 33 33 33
             | 22 22 22 12 11 11 22 12 …（下一个字形）
 0x08FE45E0: 同上头 + 另一组字形
 0x08FE4620: 22 22 22 …（纯填充，不是字）

⇒ **每字形 64 字节**：
     前 32 字节 = 固定头（0x00×8 / 0x66×4 / 0x77×4 / 0x33×4 / 8 字节填充）
     后 32 字节 = 4bpp 8×8 字形（nibble 值 1/2/3）

 ⚠ 但 32 字节只够一个 8×8，而汉字是 11×11 ⇒ 需要**多个 64 字节块拼**。

【本脚本】
 ① 验证 64 字节周期
 ② 尝试不同拼法（2 块 = 16×8？4 块 = 16×16？）
 ③ 找出真正的字库起点与总数
 ④ 导出完整字库图

用法：python scripts/research/firered/112_true_format.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
START = 0xFE4560


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 验证 64 字节周期，看「头」是不是固定")
    print("=" * 78)
    heads = []
    for k in range(12):
        off = START + k * 64
        blob = zh[off:off + 64]
        head = blob[:32]
        heads.append(head)
        u = sorted(set(v for b in blob[32:] for v in (b & 0xF, b >> 4)))
        print(f"  [{k:>2}] 0x{BASE+off:08X}")
        print(f"      头: {head.hex(' ')}")
        print(f"      字形 nibble: {u}")
    hc = Counter(h.hex() for h in heads)
    print(f"\n  头的种类：{len(hc)}")
    for h, c in hc.most_common(5):
        print(f"    ×{c}  {h}")

    # ── ② 看字形区 32 字节的内容 ───────────────────────────────
    print("\n" + "=" * 78)
    print("② 字形区（后 32 字节）画出来")
    print("=" * 78)
    for k in range(6):
        off = START + k * 64 + 32
        blob = zh[off:off + 32]
        m = nibs(blob)
        print(f"\n  [{k}] @0x{BASE+off:08X}  {blob.hex(' ')}")
        for y in range(8):
            print("    " + "".join(
                "#" if m[y, x] == 3 else ("+" if m[y, x] == 2 else
                                          ("-" if m[y, x] == 1 else "."))
                for x in range(8)))

    # ── ③ 验证「4 块拼 16×16」─────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 试「连续 4 块 = 16×16 字形」")
    print("=" * 78)
    for gi in range(3):
        cells = []
        for k in range(4):
            off = START + (gi * 4 + k) * 64 + 32
            cells.append(nibs(zh[off:off + 32]))
        cell = np.zeros((16, 16), dtype=np.uint8)
        cell[0:8, 0:8] = cells[0]
        cell[0:8, 8:16] = cells[1]
        cell[8:16, 0:8] = cells[2]
        cell[8:16, 8:16] = cells[3]
        print(f"\n  字形 {gi}:")
        for yy in range(16):
            print("    " + "".join(
                "#" if cell[yy, xx] == 3 else ("+" if cell[yy, xx] == 2
                                               else ("-" if cell[yy, xx] == 1
                                                     else "."))
                for xx in range(16)))

    # ── ④ 试「2 块上下拼 8×16」────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 试「2 块上下拼 = 8×16」")
    print("=" * 78)
    for gi in range(4):
        a = nibs(zh[START + (gi * 2) * 64 + 32: START + (gi * 2) * 64 + 64])
        b = nibs(zh[START + (gi * 2 + 1) * 64 + 32:
                    START + (gi * 2 + 1) * 64 + 64])
        print(f"\n  字形 {gi}（上下 8×16）:")
        for y in range(8):
            print("    " + "".join(
                "#" if a[y, x] == 3 else ("+" if a[y, x] == 2 else ".")
                for x in range(8)))
        for y in range(8):
            print("    " + "".join(
                "#" if b[y, x] == 3 else ("+" if b[y, x] == 2 else ".")
                for x in range(8)))

    # ── ⑤ 扫全 ROM：找同样「64 字节周期 + 固定头」的区域 ────────
    print("\n" + "=" * 78)
    print("⑤ 扫全 ROM 找同格式字库区")
    print("=" * 78)
    # 用最常见的头当特征
    if hc:
        head_hex = hc.most_common(1)[0][0]
        head_pat = bytes.fromhex(head_hex)
        print(f"  用头 {head_hex[:16]}... 当特征搜")
        hits = []
        i = zh.find(head_pat)
        while i >= 0:
            hits.append(i)
            i = zh.find(head_pat, i + 1)
        print(f"  命中 {len(hits)} 处")
        cc = Counter(h // 0x10000 for h in hits)
        for k, v in cc.most_common(8):
            print(f"    0x{BASE+k*0x10000:08X}: {v} 处")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
