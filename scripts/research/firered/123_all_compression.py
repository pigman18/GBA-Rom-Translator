#!/usr/bin/env python3
"""调研(123) 补全 GBA 四种压缩算法，找被压缩的字库。

═══════════════════════════════════════════════════════════════════════════
【(119) 只试了 LZ77，漏了其余三种】
═══════════════════════════════════════════════════════════════════════════
GBA BIOS 支持 4 种压缩，首字节高 4 位标识：
    0x1X = LZ77        （(119) 已试，1598 个块，无中文字形）
    0x2X = LZSS/LZ77 变体
    0x3X = **RLE**      ← 字库最常用！
    0x8X = Huffman

字形数据有个特点：**大片同色（底色）**，所以 **RLE 压缩率极高**。
若汉化用 RLE 存字库，1 字节头 + 数据，原始 4bpp 字节在 ROM 里根本搜不到。

【RLE (0x30) 格式】
    第 1 字节：0x30 | (解压长度高 4 位)
    后 3 字节：解压长度（24 位小端）
    数据：每「块」由 1 个标志字节 + 数据组成
        标志 bit7=1：压缩块，低 7 位 = 重复次数-1，后跟 1 字节重复值
        标志 bit7=0：原始块，低 7 位 = 字节数-1，后跟 N 字节原样

【本脚本】
 ① 实现 RLE / LZSS 解压
 ② 扫全 ROM 找这两类压缩块
 ③ 解压后用「字形判据」筛（nibble 集中、含 1 和 2、长度够 2000 字）
 ④ 找到了就画出来

用法：python scripts/research/firered/123_all_compression.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def rle_decompress(data: bytes, max_out: int = 0x200000):
    """GBA RLE (0x30) 解压。"""
    if len(data) < 4 or (data[0] >> 4) != 3:
        return None
    size = ((data[0] & 0xF) << 24) | (data[1] << 16) | \
           (data[2] << 8) | data[3]
    if size == 0 or size > max_out:
        return None
    out = bytearray()
    i = 4
    while len(out) < size:
        if i >= len(data):
            return None
        flag = data[i]
        i += 1
        n = (flag & 0x7F) + 1
        if flag & 0x80:
            if i >= len(data):
                return None
            out.extend(bytes([data[i]]) * n)
            i += 1
        else:
            if i + n > len(data):
                return None
            out.extend(data[i:i + n])
            i += n
    return bytes(out[:size])


def lzss_decompress(data: bytes, max_out: int = 0x200000):
    """GBA LZSS (0x20) 解压（LZ77 的变体，disp 用 12 位）。"""
    if len(data) < 4 or (data[0] >> 4) != 2:
        return None
    size = ((data[0] & 0xF) << 24) | (data[1] << 16) | \
           (data[2] << 8) | data[3]
    if size == 0 or size > max_out:
        return None
    out = bytearray()
    i = 4
    while len(out) < size:
        if i >= len(data):
            return None
        flags = data[i]
        i += 1
        for bit in range(7, -1, -1):
            if len(out) >= size:
                break
            if i >= len(data):
                return None
            if not (flags >> bit) & 1:
                out.append(data[i])
                i += 1
            else:
                if i + 1 >= len(data):
                    return None
                b0, b1 = data[i], data[i + 1]
                i += 2
                disp = ((b0 & 0xF) << 8) | b1
                ln = (b0 >> 4) + 3
                if disp == 0 or disp > len(out):
                    return None
                for _ in range(ln):
                    if len(out) >= size:
                        break
                    out.append(out[-disp])
    return bytes(out[:size])


def glyph_score(blob: bytes) -> tuple[float, int, int]:
    """返回 (nibble 集中度, nib1数, nib2数)。集中度 = (0+1+2 的占比)。"""
    c = {0: 0, 1: 0, 2: 0}
    other = 0
    tot = 0
    for b in blob:
        for v in (b & 0xF, b >> 4):
            tot += 1
            if v <= 2:
                c[v] += 1
            else:
                other += 1
    if tot == 0:
        return 0, 0, 0
    return (tot - other) / tot, c[1], c[2]


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    for name, fn, tag in (("RLE (0x30)", rle_decompress, 3),
                          ("LZSS (0x20)", lzss_decompress, 2)):
        print("=" * 78)
        print(f"① 扫 {name} 压缩块")
        print("=" * 78)
        found = []
        total = 0
        for off in range(0, n - 8, 4):
            if (zh[off] >> 4) != tag:
                continue
            out = fn(zh[off:off + 0x10000])
            if out is None:
                continue
            total += 1
            score, n1, n2 = glyph_score(out)
            # 字库特征：nibble 高度集中在 0/1/2，且有足够多的 1 和 2
            if score > 0.90 and n1 > 200 and n2 > 200 and len(out) >= 4096:
                found.append((off, len(out), score, n1, n2))

        print(f"  可解压块：{total}")
        print(f"  像字库的（nibble 集中在 0/1/2 且 1/2 都多）：{len(found)}")
        for off, size, score, n1, n2 in sorted(found, key=lambda x: -x[1])[:15]:
            isnew = "★汉化新增" if ja[off:off + 4] != zh[off:off + 4] else ""
            print(f"    0x{BASE+off:08X}  解压 {size:>8,} B  "
                  f"集中度 {score:.1%}  n1={n1} n2={n2}  {isnew}")

        # 画最大的
        if found:
            off, size, score, n1, n2 = max(found, key=lambda x: x[1])
            out = fn(zh[off:off + 0x10000])
            print(f"\n  最大块 0x{BASE+off:08X}（解压 {len(out):,} B）前 6 块：")
            for k in range(6):
                blob = out[k * 32:(k + 1) * 32]
                if len(blob) < 32:
                    break
                print(f"\n    块{k}:")
                for y in range(8):
                    row = blob[y * 4:(y + 1) * 4]
                    line = ""
                    for x in range(8):
                        b = row[x // 2]
                        v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                        line += "." if v == 0 else ("+" if v == 1 else
                                                    ("#" if v == 2 else str(v)))
                    print("      " + line)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
