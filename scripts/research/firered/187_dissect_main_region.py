#!/usr/bin/env python3
"""调研(187) 解剖主新增区 0x006D0000..0x00727000（356KB，新增 335KB）。

═══════════════════════════════════════════════════════════════════════════
【(186) 定位到的主战场】
═══════════════════════════════════════════════════════════════════════════
汉化新增字节 648,263，其中**最大的一块连续新增区**：
    0x006D0000 .. 0x00727000   356,352 B   新增 335,756 B

检查点里把这段当作「F7 文本区」。但账对不上：
  · 2299 字 x 64B 字库 = 147,136 B
  · 若这段全是文本，那字库在哪？
  · 若这段里混着字库，那文本只占 ~190KB？
**必须打开看。**

【本脚本的解剖手段（不预设格式）】
 A. 字节值直方图：这段里 0xF7 / 0xFF / 0x00 的密度
    → 文本区会有海量 0xF7
 B. 分段扫描：每 4KB 统计「F7 密度」「FF 密度」「可打印率」
    → 找出文本段与数据段的分界
 C. 对「非文本段」做字模特征扫描（32B 块 nibble 特征）
 D. 把「非文本段」按 32B/64B stride 直接可视化（看图）
 E. 交叉验证：这些段是否出现在 VRAM 已知字形的搜索里

【判定】
 若某段 4KB 窗口 F7 密度 <1% 且含大量 32B 结构块 → 疑似字库段
 全段 F7 都高 → 纯文本，字库在别处

用法：python scripts/research/firered/187_dissect_main_region.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "region187"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SCREEN_BASE = 0xF000

A0, A1 = 0x006D0000, 0x00727000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def save_png(path: Path, arr: np.ndarray) -> None:
    import zlib
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack(">I", len(data)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9))
                     + chunk(b"IEND", b""))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()
    vr = (SNAP / "vram.bin").read_bytes()
    seg = rom[A0:A1]
    print(f"区段 0x{A0:08X}..0x{A1:08X}  {len(seg):,} B")

    # ── A 全局直方图 ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("A 全局字节分布（只看关键值）")
    print("=" * 78)
    c = Counter(seg)
    total = len(seg)
    for v in (0xF7, 0xF6, 0xF8, 0xF9, 0xFF, 0x00):
        print(f"  0x{v:02X}: {c.get(v, 0):>8,}  ({c.get(v, 0) / total:>6.2%})")
    print(f"  不同字节值种类：{len(c)}")
    top = c.most_common(8)
    print(f"  最常见：{[hex(v) for v, _ in top]}")
    print(f"  各自占比：{[f'{n / total:.1%}' for _, n in top]}")

    # 若含 0xF7 文本，3 字节一组应有大量 F7
    n_f7 = c.get(0xF7, 0)
    print(f"\n  若全是 F7 文本（每字 3 字节）：最多可容纳 {n_f7:,} 个码位")

    # ── B 每 4KB 窗口画像 ─────────────────────────────────
    print("\n" + "=" * 78)
    print("B 每 4KB 窗口画像（F7密度 / FF密度 / 32B字模候选）")
    print("=" * 78)
    W = 0x1000
    windows = []
    for off in range(0, len(seg), W):
        w = seg[off:off + W]
        if len(w) < W:
            break
        f7 = sum(1 for b in w if b == 0xF7) / W
        ff = sum(1 for b in w if b == 0xFF) / W
        z = sum(1 for b in w if b == 0x00) / W
        # 32B 字模候选（严格判据：(184) 用过，全 ROM 只有 38 个）
        cand = 0
        for k in range(0, W - 32, 32):
            blk = w[k:k + 32]
            vals = set()
            ok = True
            for b in blk:
                vals.add(b & 0x0F)
                vals.add(b >> 4)
                if len(vals) > 6:
                    ok = False
                    break
            if ok and 2 <= len(vals) <= 4:
                vals_sorted = sorted(vals)
                # 必须是「背景占多数」
                cnt = Counter()
                for b in blk:
                    cnt[b & 0x0F] += 1
                    cnt[b >> 4] += 1
                if cnt:
                    bg = cnt.most_common(1)[0][1] / 64
                    if 0.4 <= bg <= 0.97:
                        cand += 1
        windows.append({"off": A0 + off, "f7": f7, "ff": ff, "zero": z,
                        "cand": cand})
        tag = ""
        if f7 > 0.30:
            tag = "文本"
        elif cand >= 60:
            tag = "★字模候选"
        print(f"  0x{A0 + off:08X}  F7={f7:>5.1%}  FF={ff:>5.1%}  "
              f"00={z:>5.1%}  字模块={cand:>3}/128  {tag}")

    # ── C 挑「字模候选最多」的窗口，详细看 ────────────────
    windows.sort(key=lambda d: -d["cand"])
    print("\n" + "=" * 78)
    print("C 字模候选最多的窗口（顺带看它的 F7 密度）")
    print("=" * 78)
    for w in windows[:8]:
        print(f"  0x{w['off']:08X}  字模块 {w['cand']}/128  "
              f"F7={w['f7']:.1%}  FF={w['ff']:.1%}")

    # ── D 可视化：把「F7 最低、字模块最多」的窗口画出来 ────
    best = None
    for w in windows:
        if w["f7"] < 0.05 and w["cand"] >= 40:
            best = w
            break
    if best is None and windows:
        best = windows[0]

    if best:
        print("\n" + "=" * 78)
        print(f"D 可视化 0x{best['off']:08X} 起的 4KB（按 32B stride 前 128 块）")
        print("=" * 78)
        base = best["off"]
        blocks = [rom[base + i * 32: base + (i + 1) * 32] for i in range(128)]
        SCALE = 2
        cols = 16
        rows = 8
        cw = 8 * SCALE + 2
        chh = 8 * SCALE + 2
        img = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
        for i, blob in enumerate(blocks):
            m = tile_nibs(blob)
            ry, rx = divmod(i, cols)
            for y in range(8):
                for x in range(8):
                    v = int(m[y, x])
                    # 4bpp 通用映射：0 最暗，15 最亮
                    gray = min(255, v * 17)
                    img[ry * chh + y * SCALE:ry * chh + (y + 1) * SCALE,
                        rx * cw + x * SCALE:rx * cw + (x + 1) * SCALE] = (gray, gray, gray)
        p = OUT / f"WINDOW_{base:08X}.png"
        save_png(p, img)
        print(f"  ✔ {p}")

        for i, blob in enumerate(blocks[:6]):
            m = tile_nibs(blob)
            print(f"\n  块 {i}:")
            for y in range(8):
                print("    " + "".join(f"{int(v):X}" for v in m[y]))

    # ── E 这段在原版里是什么 ──────────────────────────────
    print("\n" + "=" * 78)
    print("E 原版同区内容")
    print("=" * 78)
    orseg = rom_or[A0:A1]
    cor = Counter(orseg)
    print(f"  原版 FF: {cor.get(0xFF, 0):,} ({cor.get(0xFF, 0) / len(orseg):.1%})")
    print(f"  原版 00: {cor.get(0x00, 0):,} ({cor.get(0x00, 0) / len(orseg):.1%})")
    print(f"  原版不同值种类: {len(cor)}")

    (OUT / "windows.json").write_text(
        json.dumps({"a0": A0, "a1": A1, "windows": windows[:80]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'windows.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
