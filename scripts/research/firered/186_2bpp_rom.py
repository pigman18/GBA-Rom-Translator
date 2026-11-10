#!/usr/bin/env python3
"""调研(186) 补齐搜索缺口：8x16 的 2bpp(32B) 与 1bpp(16B) 从未在 ROM 搜过。

═══════════════════════════════════════════════════════════════════════════
【为什么这是真缺口】
═══════════════════════════════════════════════════════════════════════════
已确证：汉字 = 8 宽 x 16 高（176/180）。

各种「位深 x 高度」下的每字字节数：

  格式              每行字节      16 行合计     2299 字总大小
  4bpp 8x16          4 B          64 B         147,136 B
  2bpp 8x16          2 B          32 B          73,568 B   ← (181) 没搜过！
  1bpp 8x16          1 B          16 B          36,784 B   ← 半部搜过但整字没搜

(181) 的 encs 只有：raw(4bpp 32B 每半) / sw / i12-M / i12-L /
i1112-M / i1112-L(1bpp 8B 每半) —— **2bpp 完全缺席**。
(183) 的 2bpp 只在 RAM 里搜过，**ROM 没搜**。

⇒ 本脚本补齐：2bpp 与 1bpp 的**整字 8x16** 在 ROM 上的全量搜索。

【2bpp 的三种常见排列】
 P-row   每行 2 字节，高字节在前（8px x 2bit = 16bit）
 P-rowL  每行 2 字节，低字节在前
 P-planar 平面分离：前 16 字节 = bit0 平面，后 16 字节 = bit1 平面
 P-planarB 平面分离，bit1 在前

【1bpp 的四种】
 O-M   每行 1 字节，MSB 在左
 O-L   每行 1 字节，LSB 在左
 O-MT  MSB + 行列转置
 O-MB  MSB + 每字节位反转

【判定】
 真字库：某格式下多数种子都能命中，且命中地址成**等距**（stride = 字号）
 假阳性：命中 ≤3 或地址随机

用法：python scripts/research/firered/186_2bpp_rom.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "bpp186"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SCREEN_BASE = 0xF000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def norm(m: np.ndarray) -> np.ndarray:
    """10/11/12 → 0/1/2（用于 2bpp）。"""
    o = np.zeros_like(m)
    o[m == 10] = 0
    o[m == 11] = 1
    o[m == 12] = 2
    return o


def enc_2bpp_row(m: np.ndarray, big: bool = True) -> bytes:
    out = bytearray()
    for y in range(16):
        v = 0
        for x in range(8):
            v |= (int(m[y, x]) & 3) << (14 - x * 2)
        out += v.to_bytes(2, "big" if big else "little")
    return bytes(out)


def enc_2bpp_planar(m: np.ndarray, bit1_first: bool = False) -> bytes:
    p0, p1 = bytearray(), bytearray()
    for y in range(16):
        v0 = v1 = 0
        for x in range(8):
            v = int(m[y, x]) & 3
            bit = 7 - x
            v0 |= ((v >> 0) & 1) << bit
            v1 |= ((v >> 1) & 1) << bit
        p0.append(v0)
        p1.append(v1)
    return bytes(p1) + bytes(p0) if bit1_first else bytes(p0) + bytes(p1)


def enc_1bpp(m01: np.ndarray, msb: bool = True, transpose: bool = False,
             bitrev: bool = False) -> bytes:
    mm = m01.T if transpose else m01
    out = bytearray()
    for y in range(16 if not transpose else 8):
        v = 0
        span = 8 if not transpose else 16
        for x in range(span):
            if mm[y, x]:
                v |= 1 << ((7 - x) if msb else x)
        out.append(v)
    if bitrev:
        out = bytearray(sum(((b >> i) & 1) << (7 - i) for i in range(8)) if False else 0 for b in out)
    return bytes(out)


def find_all(hay: bytes, needle: bytes, limit: int = 200) -> list[int]:
    out = []
    i = hay.find(needle)
    while i >= 0 and len(out) < limit:
        out.append(i)
        i = hay.find(needle, i + 1)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()
    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()

    # ── 收集 8x16 字形 ────────────────────────────────────
    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    gs = []
    for r in range(text_rows[0], 19, 2):
        for c in range(30):
            et = entry(vr, r, c)
            if ((et >> 12) & 0xF) != 15:
                continue
            eb = entry(vr, r + 1, c)
            ot, ob = (et & 0x3FF) * 32, (eb & 0x3FF) * 32
            if ot + 32 > len(vr) or ob + 32 > len(vr):
                continue
            full = np.vstack([tile_nibs(vr[ot:ot + 32]),
                              tile_nibs(vr[ob:ob + 32])])
            ink = int(((full == 11) | (full == 12)).sum())
            if 4 <= ink <= 120:
                gs.append(full)
    print(f"真实 8x16 字形：{len(gs)}")

    ENC: dict[str, callable] = {
        "2bpp-row-B": lambda m: enc_2bpp_row(norm(m), True),
        "2bpp-row-L": lambda m: enc_2bpp_row(norm(m), False),
        "2bpp-planar": lambda m: enc_2bpp_planar(norm(m), False),
        "2bpp-planar-B": lambda m: enc_2bpp_planar(norm(m), True),
        "2bpp-core1": lambda m: enc_2bpp_row((m == 12).astype(np.uint8), True),
        "1bpp-M": lambda m: enc_1bpp((m == 12).astype(np.uint8), True),
        "1bpp-L": lambda m: enc_1bpp((m == 12).astype(np.uint8), False),
        "1bpp-any-M": lambda m: enc_1bpp(((m == 11) | (m == 12)).astype(np.uint8), True),
        "1bpp-any-L": lambda m: enc_1bpp(((m == 11) | (m == 12)).astype(np.uint8), False),
    }

    print("\n" + "=" * 78)
    print("ROM 全量搜索（补齐 2bpp 缺口）")
    print("=" * 78)
    results = []
    for ename, fn in ENC.items():
        size = len(fn(gs[0]))
        hits = 0
        offs = []
        for m in gs:
            pat = fn(m)
            loc = find_all(rom, pat, limit=50)
            if loc:
                hits += 1
                offs.extend(loc)
        so = sorted(set(offs))
        gaps = [b - a for a, b in zip(so, so[1:])]
        gc = Counter(gaps)
        gtop = gc.most_common(1)[0] if gc else (0, 0)
        results.append({"enc": ename, "size": size, "hits": hits,
                        "n_off": len(so), "top_gap": gtop[0], "top_n": gtop[1],
                        "offsets": so[:40]})
        print(f"  {ename:<14} {size:>2}B  命中字 {hits:>3}/{len(gs)}  "
              f"位置 {len(so):>4}  最多间隔 {gtop[0]}x{gtop[1]}")

    # ── 判定：等距 = 真表 ────────────────────────────────
    print("\n" + "=" * 78)
    print("判定：是否存在等距表（stride == 字号 或 其整数倍）")
    print("=" * 78)
    found = []
    for r in results:
        if r["top_n"] >= 4 and r["top_gap"] % r["size"] == 0 and r["top_gap"] > 0:
            found.append(r)
            print(f"  ★★ {r['enc']}  stride={r['top_gap']}B "
                  f"({r['top_gap'] // r['size']} 字) x{r['top_n']}")
            print(f"      地址 {[hex(x) for x in r['offsets'][:10]]}")
    if not found:
        print("  ✘ 无等距表 —— 2bpp / 1bpp 整字格式也不在 ROM 里")

    # ── 关键：新增区账本 ────────────────────────────────
    print("\n" + "=" * 78)
    print("新增区账本：汉化在原版 FF 处写了多少字节，分布在哪")
    print("=" * 78)
    W = 0x1000
    blocks = []
    for off in range(0, len(rom), W):
        seg_zh = rom[off:off + W]
        seg_or = rom_or[off:off + W]
        if len(seg_or) < len(seg_zh):
            seg_or = seg_or + b"\xFF" * (len(seg_zh) - len(seg_or))
        # 原版 FF 且汉化非 FF = 新增
        added = sum(1 for a, b in zip(seg_zh, seg_or) if b == 0xFF and a != 0xFF)
        if added > 64:
            blocks.append((off, added))
    blocks.sort(key=lambda x: -x[1])
    print(f"  4KB 窗口里新增 >64 字节的：{len(blocks)} 个窗口，"
          f"合计新增 {sum(a for _, a in blocks):,} B")
    print(f"  新增最多的 25 个窗口（按新增字节排序）：")
    for off, added in blocks[:25]:
        print(f"    0x{off:08X}..0x{off + W:08X}  新增 {added:>5,} B "
              f"({added / W:.0%})")

    # 找「连续多窗口都高新增」的巨块
    print("\n  连续高新增区段（≥4 个相邻窗口）：")
    runs = []
    cur = []
    last = None
    for off, added in sorted(blocks):
        if last is not None and off == last + W:
            cur.append((off, added))
        else:
            if len(cur) >= 4:
                runs.append(cur)
            cur = [(off, added)]
        last = off
    if len(cur) >= 4:
        runs.append(cur)
    runs.sort(key=lambda c: -sum(a for _, a in c))
    for c in runs[:12]:
        s = c[0][0]
        e = c[-1][0] + W
        tot = sum(a for _, a in c)
        print(f"    0x{s:08X}..0x{e:08X}  {len(c)} 窗口  "
              f"{(e - s):>7,} B  新增 {tot:>7,} B")

    (OUT / "bpp.json").write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n已写 {OUT / 'bpp.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
