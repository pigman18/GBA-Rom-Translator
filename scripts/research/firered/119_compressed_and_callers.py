#!/usr/bin/env python3
"""调研(119) 两条漏掉的线：压缩字库 + 搬运函数的真实调用者。

═══════════════════════════════════════════════════════════════════════════
【用户提醒的关键】
═══════════════════════════════════════════════════════════════════════════
「哪怕是 VRAM 生成的，在生成前肯定也有块静态地方的」

⇒ 我一直在搜「解压后的 4bpp 字形」，但若 ROM 里存的是**压缩数据**，
   原始字节当然搜不到。GBA 的 BIOS 自带 LZ77/LZSS/RLE 解压。

【两条线索】

 线 A：**压缩数据**
   GBA LZ77 压缩块的标准头：
     第 1 字节 = 0x10 | (解压长度的高 4 位)  ← 高 4 位必为 0x1
     后 3 字节 = 解压长度（24 位小端）
   判据：扫 ROM 找「首字节高 4 位 = 1，且解压长度合理」的块，
        再试着解压，看结果是不是 4bpp 字形。

 线 B：**搬运函数 0x08FE4814 的调用者**
   (111) 搜 bl 跳向它 → 0 个。这不正常。
   可能：
     · 用 `bx rX` 间接跳（函数指针）
     · 用 `blx rX`
     · 我搜 bl 时只按 2 字节对齐，但 Thumb bl 实际是 4 字节对齐的指令对
       （地址必须是偶数，我按 2 对齐是对的，但漏了奇数起点也无意义）
     · 或者它根本不被调用，是数据被误认为代码

   做法：搜所有指向 0x08FE48xx 的**指针**（u32），以及 `ldr rX,[pc,#n]` +
        `bx rX` 组合。

【本脚本】
 ① 扫 ROM 找 LZ77 压缩块（含汉化新增区），解压并检查是否是字形
 ② 更彻底地找 0x08FE4814 的引用（指针 / bx / blx）

用法：python scripts/research/firered/119_compressed_and_callers.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def lz77_decompress(data: bytes, max_out: int = 0x100000):
    """GBA BIOS LZ77 (0x10) 解压。返回 bytes 或 None。"""
    if len(data) < 4:
        return None
    if (data[0] >> 4) != 1:
        return None
    size = data[0] & 0xF
    size = (size << 8) | data[1]
    size = (size << 8) | data[2]
    size = (size << 8) | data[3]
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
    return bytes(out)


def is_glyph_data(blob: bytes) -> tuple[bool, int, int]:
    """判断一段数据像不像 4bpp 字形集（nibble 主要在 0/1/2，含 1 和 2）。"""
    n1 = n2 = bad = 0
    for b in blob:
        for v in (b & 0xF, b >> 4):
            if v == 0:
                continue
            elif v == 1:
                n1 += 1
            elif v == 2:
                n2 += 1
            else:
                bad += 1
    tot = n1 + n2 + bad
    if tot == 0:
        return False, 0, 0
    ok = (bad < tot * 0.05) and n1 > tot * 0.05 and n2 > tot * 0.05
    return ok, n1, n2


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("线 A：扫 ROM 找 LZ77 压缩块，解压后看是不是字形")
    print("=" * 78)
    hits = []
    for off in range(0, n - 8, 4):
        b0 = zh[off]
        if (b0 >> 4) != 1:
            continue
        # 解压长度
        size = ((b0 & 0xF) << 24) | (zh[off + 1] << 16) | \
               (zh[off + 2] << 8) | zh[off + 3]
        if size < 256 or size > 0x40000:
            continue
        out = lz77_decompress(zh[off:off + size * 2 + 64])
        if out is None or len(out) != size:
            continue
        ok, n1, n2 = is_glyph_data(out)
        if ok:
            hits.append((off, size, n1, n2, out))

    print(f"  「解压后像字形」的 LZ77 块：{len(hits)}")
    for off, size, n1, n2, out in sorted(hits, key=lambda x: -x[1])[:15]:
        isnew = "★汉化新增" if ja[off:off + 4] != zh[off:off + 4] else ""
        print(f"    0x{BASE+off:08X}  解压 {size:>7,} B  "
              f"n1={n1} n2={n2}  {isnew}")

    # ── 若找到，展开看 ────────────────────────────────────────
    if hits:
        off, size, n1, n2, out = max(hits, key=lambda x: x[1])
        print(f"\n  最大块 0x{BASE+off:08X} 解压后前 6 个 32B 块：")
        for k in range(6):
            blob = out[k * 32:(k + 1) * 32]
            if len(blob) < 32:
                break
            print(f"\n    块{k}: {blob[:16].hex(' ')}")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else ("+" if v == 1 else "#")
                print("      " + line)

    # ── 也统计所有 LZ77 块（不论内容）─────────────────────────
    print("\n" + "=" * 78)
    print("  所有能成功解压的 LZ77 块统计")
    print("=" * 78)
    alllz = 0
    byzone = {}
    for off in range(0, n - 8, 4):
        b0 = zh[off]
        if (b0 >> 4) != 1:
            continue
        size = ((b0 & 0xF) << 24) | (zh[off + 1] << 16) | \
               (zh[off + 2] << 8) | zh[off + 3]
        if size < 256 or size > 0x40000:
            continue
        out = lz77_decompress(zh[off:off + size * 2 + 64])
        if out is None or len(out) != size:
            continue
        alllz += 1
        z = off // 0x10000
        byzone[z] = byzone.get(z, 0) + 1
    print(f"  可解压块总数：{alllz}")
    for z, c in sorted(byzone.items(), key=lambda x: -x[1])[:10]:
        print(f"    0x{BASE+z*0x10000:08X}: {c}")

    # ── 线 B：找 0x08FE4814 的引用 ────────────────────────────
    print("\n" + "=" * 78)
    print("线 B：找 0x08FE4814（字形搬运函数）的所有引用")
    print("=" * 78)
    m = n // 4 * 4
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    for tgt in range(0x8FE4800, 0x8FE4860, 2):
        h = np.flatnonzero(pz == tgt)
        if len(h):
            print(f"  指针 0x{tgt:08X}: {len(h)} 处 → "
                  f"{[f'0x{BASE+x*4:08X}' for x in h[:5]]}")
    # 也搜奇数地址的指针（Thumb 位）
    h2 = np.flatnonzero((pz >= 0x8FE4801) & (pz <= 0x8FE4861))
    if len(h2):
        print(f"  Thumb 位指针：{len(h2)} 处")
        for x in h2[:10]:
            print(f"    0x{BASE+x*4:08X} → 0x{int(pz[x]):08X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
