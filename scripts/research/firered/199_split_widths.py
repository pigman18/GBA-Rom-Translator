#!/usr/bin/env python3
"""调研(199) 精确分离三套字宽：12 / 10 / 原版借用（含 2 宽）。

═══════════════════════════════════════════════════════════════════════════
【(197) 实测确认（用户假设成立）】
═══════════════════════════════════════════════════════════════════════════
  行 r=1（「继续游戏」）：段宽全 = 12，pitch 全 = 13
  ⇒ **汉字主字宽 = 12px，字距 13px（12 墨 + 1 间隙）**

  行 r=3（「时间 22:04」）：段宽 = 11 / 6 / 6 / 6，pitch = 7 / 7
  ⇒ **半角数字/符号宽度小得多，且 pitch 不同 ⇒ 这是「借用原版字形」的证据**

  与 (192) 反汇编 `cmp r1,#0xA0 → 12 / 10 / 2` 三档完全对应。

【本脚本要精确回答的三个问题】
 Q1 每个字形**真实占用几个 VRAM tile**（12 宽必然跨 2 个 tile）
 Q2 12 宽 / 10 宽 / 窄字 各有多少个，能否按字形分离
 Q3 **半角字（RED / 22:04）是否来自原版字库** —— 用原版 ROM 验证

【方法：按 pitch 而非按空隙切分】
 197 用「连续零列」切分，会把 12 宽字切成 8+4 两段（因为 tile 边界处
 如果恰好是零列就会误切）。正确做法是：
   ① 先按 tilemap 得到每个「字符格」的起始 x = col * 8
   ② 但字宽 12 > 8 ⇒ 字符格与字形不是一一对应
   ③ 改用：先求整行墨迹的「每 13 像素」周期（主字宽）
   ④ 再对非 13 周期的区域单独处理

更稳的做法：**用 197 已验证的段宽 + pitch 直接定位**，
不重新切分，只统计与归类。

用法：python scripts/research/firered/199_split_widths.py
"""
from __future__ import annotations

import json
import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "widths199"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SCREEN_BASE = 0xF000
INK = {11, 12}


def save_png(path: Path, arr: np.ndarray) -> None:
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


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def build_row(vr: bytes, r: int) -> np.ndarray:
    W = 30 * 8
    canvas = np.zeros((16, W), dtype=np.uint8)
    for c in range(30):
        et = entry(vr, r, c)
        eb = entry(vr, r + 1, c)
        for half, e in ((0, et), (1, eb)):
            t = e & 0x3FF
            o = t * 32
            if o + 32 > len(vr):
                continue
            canvas[half * 8:(half + 1) * 8, c * 8:(c + 1) * 8] = \
                tile_nibs(vr[o:o + 32])
    return canvas


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()

    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    start = text_rows[0]

    print("=" * 78)
    print("Q1 每行字形按「非零列游程」精确切分（不用零列切，用游程）")
    print("=" * 78)

    all_rows = []
    for r in range(start, 19, 2):
        canvas = build_row(vr, r)
        ink = np.isin(canvas, list(INK))
        col = ink.sum(axis=0)
        nz = col > 0
        if not nz.any():
            continue
        xs = np.flatnonzero(nz)
        segs = []
        a = xs[0]
        prev = xs[0]
        for x in xs[1:]:
            if x - prev > 1:
                segs.append((a, prev + 1))
                a = x
            prev = x
        segs.append((a, prev + 1))
        all_rows.append({"r": r, "segs": segs, "canvas": canvas})

        widths = [b - a for a, b in segs]
        print(f"\n  r={r}  段数={len(segs)}")
        print(f"    段: {segs}")
        print(f"    宽: {widths}   分布={dict(Counter(widths))}")

    # ── Q1b：12 宽字必然跨 2 tile，检查是否被切成 8+4 ─────
    print("\n" + "=" * 78)
    print("Q1b 是否有「8 + 4」被误切的情况（12 宽字跨 tile 边界的痕迹）")
    print("=" * 78)
    split_84 = 0
    for row in all_rows:
        ws = [b - a for a, b in row["segs"]]
        for i in range(len(ws) - 1):
            if ws[i] == 8 and ws[i + 1] == 4:
                split_84 += 1
    print(f"  出现「宽8 + 宽4」相邻的次数：{split_84}")
    if split_84 == 0:
        print("  ⇒ 没有 8+4 误切，说明 12 宽字是**整体连续**的，")
        print("     即 VRAM 里 12px 字模已按 12 宽排好（跨 tile 但连续）")

    # ── Q2：宽度归类 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("Q2 全部字形按宽度归类")
    print("=" * 78)
    wc = Counter()
    for row in all_rows:
        for a, b in row["segs"]:
            wc[b - a] += 1
    print(f"  宽度分布：{dict(sorted(wc.items()))}")
    print(f"  宽 12（汉字主档）：{wc.get(12, 0)}")
    print(f"  宽 11          ：{wc.get(11, 0)}")
    print(f"  宽 10          ：{wc.get(10, 0)}")
    print(f"  宽 <=8（窄字）  ：{sum(v for k, v in wc.items() if k <= 8)}")

    # ── Q3：窄字是否来自原版 ────────────────────────────
    print("\n" + "=" * 78)
    print("Q3 窄字（半角字母/数字）是否来自原版 ROM 字库")
    print("=" * 78)
    # 取一个窄字段落，尝试在原版 ROM 里找它的 8x8/8x16 位图
    narrow_found = 0
    narrow_tried = 0
    for row in all_rows:
        canvas = row["canvas"]
        for a, b in row["segs"]:
            w = b - a
            if w > 8:
                continue
            # 补齐到 8 宽
            pad = np.zeros((16, 8), dtype=np.uint8)
            pad[:, :w] = canvas[:, a:b]
            narrow_tried += 1
            # 打 4bpp 32B（上半）与 64B（全）
            def pack(mat, rows=8):
                out = bytearray()
                for y in range(rows):
                    for xb in range(4):
                        hi = int(mat[y, xb * 2])
                        lo = int(mat[y, xb * 2 + 1])
                        out.append((hi << 4) | lo)
                return bytes(out)
            for variant, data in (("half_nib", pack(pad, 8)),
                                  ("full_nib", pack(pad, 16)),
                                  ("zero_bg_half", bytes(
                                      ((int(pad[y, xb * 2]) if pad[y, xb * 2] in (11, 12) else 0) << 4)
                                      | (int(pad[y, xb * 2 + 1]) if pad[y, xb * 2 + 1] in (11, 12) else 0)
                                      for y in range(8) for xb in range(4)))):
                if len(data) and (zh.find(data) >= 0 or ja.find(data) >= 0):
                    narrow_found += 1
                    where = "汉化" if zh.find(data) >= 0 else "原版"
                    print(f"    宽{w} 段 {a}..{b} [{variant}] 命中 {where}")
                    break
    print(f"  窄字共试 {narrow_tried} 个，命中 {narrow_found} 个")
    if narrow_found == 0:
        print("  ⇒ 窄字也不是直接以 4bpp 存于 ROM")

    # ── 输出：按宽度分层的三段图 ─────────────────────────
    print("\n" + "=" * 78)
    print("输出分层图：12宽一组 / 11宽一组 / 窄字一组")
    print("=" * 78)
    SCALE = 4
    colors = {0: (45, 45, 45), 10: (12, 12, 12),
              11: (165, 165, 165), 12: (250, 250, 250)}
    for label, lo, hi in (("W12", 12, 99), ("W11", 11, 11),
                          ("W10", 10, 10), ("NARROW", 1, 9)):
        picked = []
        for row in all_rows:
            for a, b in row["segs"]:
                if lo <= b - a <= hi:
                    picked.append(row["canvas"][:, a:b])
        if not picked:
            continue
        mw = max(m.shape[1] for m in picked)
        per = 12
        rows_n = (len(picked) + per - 1) // per
        cw = mw * SCALE + 6
        chh = 16 * SCALE + 6
        img = np.full((rows_n * chh, per * cw, 3), 14, dtype=np.uint8)
        for i, m in enumerate(picked):
            ry, rx = divmod(i, per)
            y0 = ry * chh + 3
            x0 = rx * cw + 3
            for y in range(16):
                for x in range(m.shape[1]):
                    img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                        x0 + x * SCALE:x0 + (x + 1) * SCALE] = \
                        colors.get(int(m[y, x]), (255, 0, 0))
        p = OUT / f"{label}.png"
        save_png(p, img)
        print(f"  ✔ {label}: {len(picked)} 字 → {p.name} "
              f"({img.shape[1]}x{img.shape[0]})")

    (OUT / "rows.json").write_text(
        json.dumps([{"r": r["r"], "segs": r["segs"]} for r in all_rows],
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
