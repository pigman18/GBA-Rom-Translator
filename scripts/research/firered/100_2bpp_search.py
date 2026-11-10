#!/usr/bin/env python3
"""调研(100) 用「VRAM 抗锯齿模式」反查 ROM —— 找字形源数据。

═══════════════════════════════════════════════════════════════════════════
【已确证的事实（可作锚点）】
═══════════════════════════════════════════════════════════════════════════
 Y1 VRAM 里文字字形的 nibble 只有 **10 / 11 / 12** 三种（白 / 浅灰 / 深灰）
 Y2 tile 2 的原始字节：
      aa aa aa aa aa aa aa aa aa aa aa aa ba ac aa aa
      bc bc ac aa bb bc ac aa bc cb ac ba bb bb cb ba
    其中 0xAA = nibble(10,10)、0xBA = (10,11)、0xAC = (10,12)
    ⇒ **每一对 nibble 是 (10,x)**，说明是「白底 + 灰度笔画」
 Y3 完整 32 字节在 ROM 里搜不到（(96) 已测）
 Y4 但 nibble 模式（0xAA/0xBA/0xAC 的序列）可能以**别的位宽**存在

【关键洞察：字形可能是 2bpp】
 若 ROM 存 2bpp（每像素 2 bit），则 4 个像素 = 1 字节。
 VRAM 里 nibble 10/11/12 的 2bpp 原值可能是 2/1/0（3 级灰度）。
 即 ROM 里 2bpp 的 `00/01/10` → 上屏时映射成 nibble `12/11/10`。

 2bpp 8×8 = 16 字节/字；11×11 时约 22~32 字节。
 这正好落在 (99) 那些「填充率 29~36%」的候选区里！

【本脚本】
 ① 构造「2bpp 版」的参考模式：从 VRAM 的 tile 2 反推 2bpp
 ② 在 ROM 里搜 2bpp 形式的字节
 ③ 若命中，验证该区能否画出汉字

用法：python scripts/research/firered/100_2bpp_search.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "work" / "_probe" / "glyphs"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000


def main() -> int:
    vram = (G / "g1.vram.bin").read_bytes()
    zh = FR_ZH.read_bytes()

    print("=" * 78)
    print("① VRAM tile 2 的 nibble 图（这是已知的一个汉字块）")
    print("=" * 78)
    t = 2
    blob = vram[t * 32:(t + 1) * 32]
    nib = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            nib[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    print("  nibble 图：")
    for y in range(8):
        print("    " + " ".join(f"{nib[y, x]:>2}" for x in range(8)))

    # 唯一值
    print(f"\n  唯一 nibble：{sorted(set(nib.flatten().tolist()))}")

    # ── ② 转成 2bpp（白=0, 浅灰=1, 深灰=2）──────────────────────
    print("\n" + "=" * 78)
    print("② 把 nibble 映射成 2bpp 值（10→0, 11→1, 12→2）")
    print("=" * 78)
    mp = {10: 0, 11: 1, 12: 2, 0: 0}
    b2 = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b2[y, x] = mp.get(int(nib[y, x]), 0)
    print("  2bpp 图：")
    for y in range(8):
        print("    " + " ".join(str(b2[y, x]) for x in range(8)))

    # GBA 2bpp 打包：每字节 4 像素，从左到右高位到低位
    packed_hi = []
    for y in range(8):
        row = 0
        for x in range(8):
            row = (row << 2) | int(b2[y, x])
        packed_hi.append(row.to_bytes(2, "big"))
    packed = b"".join(packed_hi)
    print(f"\n  打包后（每行 2 字节，高位在前）：{packed.hex(' ')}")

    # 也试低位在前
    packed_lo = []
    for y in range(8):
        row = 0
        for x in range(7, -1, -1):
            row = (row << 2) | int(b2[y, x])
        packed_lo.append(row.to_bytes(2, "big"))
    packed2 = b"".join(packed_lo)
    print(f"  反向打包：{packed2.hex(' ')}")

    # ── ③ 在 ROM 里搜 ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 在 ROM 里搜这些 2bpp 形式")
    print("=" * 78)
    for name, pat in (("高位在前", packed[:8]), ("低位在前", packed2[:8])):
        hits = []
        i = zh.find(pat)
        while i >= 0 and len(hits) < 10:
            hits.append(i)
            i = zh.find(pat, i + 1)
        print(f"  {name} 前8字节 {pat.hex()}: {len(hits)} 处"
              + (f"  {[f'0x{BASE+x:08X}' for x in hits[:5]]}" if hits else ""))

    # ── ④ 换个思路：搜「抗锯齿环」特征 ───────────────────────────
    print("\n" + "=" * 78)
    print("④ 搜「深灰紧邻浅灰」的模式（抗锯齿的通用特征）")
    print("=" * 78)
    # 在 4bpp 字节里，0xBA = (10,11) 白+浅灰；0xAC = (10,12) 白+深灰
    # 组合 0xBA/0xAC/0xCB 等
    pats = {
        "BAAC": bytes.fromhex("baac"),
        "ACBA": bytes.fromhex("acba"),
        "CBCB": bytes.fromhex("cbcb"),
        "AA BA": bytes.fromhex("aa ba"),
    }
    for name, pat in pats.items():
        cnt = zh.count(pat)
        print(f"  {name}: {cnt:,} 次")

    # ── ⑤ 检查 VRAM 里字形的 tile 编号范围 ───────────────────────
    print("\n" + "=" * 78)
    print("⑤ 菜单用到多少种字形（tilemap 里 pal=15 的 tile 集合）")
    print("=" * 78)
    import struct
    def rd16(b, o):
        return struct.unpack_from("<H", b, o)[0]
    sb = 0xF000
    tiles = set()
    for r in range(20):
        for c in range(30):
            e = rd16(vram, sb + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) == 15:
                tiles.add(e & 0x3FF)
    print(f"  用到 {len(tiles)} 个 tile，编号 {sorted(tiles)[:30]}...")
    print(f"  ⇒ 每个汉字 2 tile（上下各一），故约 {len(tiles)//2} 个字形")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
