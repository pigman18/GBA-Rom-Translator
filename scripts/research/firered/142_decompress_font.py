#!/usr/bin/env python3
"""调研(142) 定案：解压 ROM 0x083Cxxxx 的 LZ77 数据 —— 那就是中文字库。

═══════════════════════════════════════════════════════════════════════════
【(141) 抓到的铁证】
═══════════════════════════════════════════════════════════════════════════
watchpoint 命中的 EWRAM 写入，寄存器 r0 全是 ROM 地址：

    r0=0x083CAAC4 → 10 00 11 00 3c ee ee f0 01 f0 01 f0 01 30 01 ae ec ...
    r0=0x083CB5EC → 10 80 08 00 30 00 00 f0 01 90 01 ee 53 e3 ee 04 ee 33 ...
    r0=0x083CC82C → 10 40 15 00 3a 00 00 f0 01 f0 01 60 01 30 c0 03 ...
    r0=0x083CBA68 → 10 00 10 00 3f 00 00 f0 01 f0 01 f0 01 f0 01 f0 01 ...
    r0=0x083CA1BE → (另一处)
    r0=0x083CEF6F → 00 10 00 10 00 3f 00 50 f0 01 f0 01 ...

**每个都以 `10 XX YY 00` 开头 = GBA BIOS 的 LZ77 压缩头！**
    第 1 字节 0x10 = LZ77 类型
    第 2-4 字节 = 解压后长度（24 位小端）

   例：0x083CAAC4: 10 00 11 00 → 长度 = 0x001100 = 4352 字节
   例：0x083CB5EC: 10 80 08 00 → 长度 = 0x000880 = 2176 字节
   例：0x083CC82C: 10 40 15 00 → 长度 = 0x001540 = 5440 字节

【为什么 (119) 没找到】
 (119) 的判据是「解压后像字形」= nibble 必须集中在 0/1/2 且 1、2 都多。
 但抗锯齿字形用 0/1/2/3，且有些块只有 1 没有 2 ⇒ **判据太严，全被过滤掉**。

【本脚本】
 ① 扫 0x083C0000 区，找所有 LZ77 头
 ② 解压，看内容是不是字形
 ③ 拼成完整字库

用法：python scripts/research/firered/142_decompress_font.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def lz77_decompress(data: bytes, want: int | None = None):
    """GBA LZ77 (0x10) 解压。"""
    if len(data) < 4 or (data[0] >> 4) != 1:
        return None
    size = ((data[0] & 0xF) << 24) | (data[1] << 16) | \
           (data[2] << 8) | data[3]
    if size == 0 or size > 0x100000:
        return None
    out = bytearray()
    i = 4
    guard = 0
    while len(out) < size:
        guard += 1
        if guard > size * 2 + 1000 or i >= len(data):
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
    return bytes(out)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 扫 0x083C0000 区所有 LZ77 块")
    print("=" * 78)
    blocks = []
    off = 0x3C0000
    end = 0x3F0000
    while off < end:
        if (zh[off] >> 4) == 1:
            size = ((zh[off] & 0xF) << 24) | (zh[off + 1] << 16) | \
                   (zh[off + 2] << 8) | zh[off + 3]
            if 512 <= size <= 0x100000:
                out = lz77_decompress(zh[off:off + size * 2 + 128])
                if out is not None and len(out) == size:
                    isnew = "★新增" if ja[off:off + 4] != zh[off:off + 4] else ""
                    blocks.append((off, size, out, isnew))
        off += 4

    print(f"  成功解压 {len(blocks)} 个块")
    print(f"  {'地址':>14} {'解压大小':>10} {'标记':>6}")
    for off, size, out, tag in blocks[:20]:
        print(f"  0x{BASE+off:08X} {size:>10,} {tag:>6}")

    total = sum(b[1] for b in blocks)
    print(f"\n  合计解压 {total:,} 字节")
    print(f"  若每字 128B → {total//128} 个字")

    # ── ② 检查内容是否含字形 nibble ──────────────────────────
    print("\n" + "=" * 78)
    print("② 检查解压内容里的 nibble 分布")
    print("=" * 78)
    for off, size, out, tag in blocks[:8]:
        seg = np.frombuffer(out, dtype=np.uint8)
        hi = seg >> 4
        lo = seg & 0x0F
        c1 = int(((hi == 1) | (lo == 1)).sum())
        c2 = int(((hi == 2) | (lo == 2)).sum())
        c3 = int(((hi == 3) | (lo == 3)).sum())
        print(f"  0x{BASE+off:08X} {size:>7,}B  "
              f"nib1={c1:>6} nib2={c2:>6} nib3={c3:>6}")

    # ── ③ 画出最大的块 ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 画最大块的前 8 个 32B tile")
    print("=" * 78)
    if blocks:
        off, size, out, tag = max(blocks, key=lambda x: x[1])
        print(f"  块 0x{BASE+off:08X}  解压 {size:,} B  {tag}")
        for k in range(8):
            blob = out[k * 32:(k + 1) * 32]
            if len(blob) < 32:
                break
            u = sorted(set(v for b in blob for v in (b & 0xF, b >> 4)))
            print(f"\n    tile {k}  nibble={u}")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else ("#" if v >= 12 else
                                                ("+" if v == 11 else str(v)))
                print("      " + line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
