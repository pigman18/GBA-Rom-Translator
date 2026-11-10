#!/usr/bin/env python3
"""调研(198) 按正确字宽重新提取字形 —— 12px / 10px / 窄字 三套。

═══════════════════════════════════════════════════════════════════════════
【(197) 实测数据（用户假设被证实）】
═══════════════════════════════════════════════════════════════════════════
  字距 pitch 分布：13 x10（主）, 9 x4, 7 x2, 6 x2, 8 x2, 其他零星
  段宽分布      ：12 x16（主）, 11 x3, 7 x7, 6 x3, 3 x1, 1 x12（零星噪点）
  墨迹纵向      ：y 0..15（高 16）

⇒ **汉字主字宽 = 12px，字距 13px**（12 墨 + 1 间隙）
  另有 7/6/3 等窄字（半角数字、标点）
  与 (192) 反汇编 `cmp r1,#0xA0 → 12 / 10 / 2` 的三档吻合：
      宽 12 = 常态汉字
      宽 10 = 部分字
      宽 2  = 极窄（空格/句点）

【此前所有搜索失败的根本原因】
 (176)(180) 我一直按 **8px（一个 tile）** 切字形，
 而汉字宽 12px ⇒ 我拿到的是**左 8px 的残片**
（右边 4px 在下一个 tile 里），拿去 ROM 搜必然 0 命中。

【本脚本】
 ① 用列投影切出每个字的精确 (起点, 宽度)
 ② 按 12 / 10 / 窄 三套分别打包成 4bpp 位图
    12 宽 x 16 高 4bpp = 16 行 x 6 字节 = **96 字节**
    10 宽 x 16 高 4bpp = 16 行 x 5 字节 = **80 字节**
 ③ 用这些**完整**字形去 ROM 全量搜索（多种编码）
 ④ 输出一张真正的完整字库 PNG（按 12px 网格重排）

【打包规则（12 宽 4bpp，行主序，每行 6 字节）】
 每个 nibble 一个像素，x=0..11，行内从左到右填，
 第 11 像素占第 6 字节的低 4 位（高 4 位补 0 或补背景值）。

用法：python scripts/research/firered/198_true_width_glyphs.py
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
OUT = ROOT / "work" / "_probe" / "truewidth198"
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


def pack_row4(row: np.ndarray, npx: int, padval: int = 10) -> bytes:
    """把 npx 宽的 nibble 行打包成字节（4bpp，左高右低）。"""
    out = bytearray()
    vals = [int(v) for v in row[:npx]] + [padval] * (npx % 2)
    for k in range(0, len(vals), 2):
        out.append((vals[k] << 4) | vals[k + 1])
    return bytes(out)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()
    rom = ROM_ZH.read_bytes()

    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    start = text_rows[0]

    all_glyphs = []      # {w, mat, row, x0, kind}
    for r in range(start, 19, 2):
        # 整幅 240 x 16
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

        ink = np.isin(canvas, list(INK))
        col = ink.sum(axis=0)
        nz = col > 0

        # 切段（用「至少 2 列连续零」作为分隔，避免把字内空隙切开）
        segs = []
        i = 0
        while i < W:
            if not nz[i]:
                i += 1
                continue
            j = i
            while j < W:
                if not nz[j]:
                    # 往后看是否有连续 2 列零
                    k = j
                    while k < W and not nz[k]:
                        k += 1
                    if k - j >= 2:
                        break
                    j = k
                else:
                    j += 1
            segs.append((i, j))
            i = j

        for (a, b) in segs:
            w = b - a
            if w < 3:
                continue
            mat = canvas[:, a:b]
            all_glyphs.append({"row": r, "x0": a, "w": w, "mat": mat})

    print(f"共切出字形 {len(all_glyphs)} 个")
    print(f"宽度分布：{dict(Counter(g['w'] for g in all_glyphs).most_common(12))}")

    # ── 按宽度分组 ──────────────────────────────────────
    groups: dict[str, list] = {"12": [], "11": [], "10": [], "9": [],
                               "narrow": []}
    for g in all_glyphs:
        w = g["w"]
        if w >= 12:
            groups["12"].append(g)
        elif w == 11:
            groups["11"].append(g)
        elif w == 10:
            groups["10"].append(g)
        elif w in (8, 9):
            groups["9"].append(g)
        else:
            groups["narrow"].append(g)
    for k, v in groups.items():
        print(f"  宽 {k:<7}: {len(v)} 个")

    # ── 输出完整字库 PNG（按真实宽度并排，不做整齐网格）──────
    SCALE = 4
    gap = 2
    # 每行放 24 个字
    per_row = 24
    rows_needed = (len(all_glyphs) + per_row - 1) // per_row
    maxw = max((g["w"] for g in all_glyphs), default=12)
    cellw = maxw * SCALE + gap * 2
    cellh = 16 * SCALE + gap * 2
    img = np.full((rows_needed * cellh, per_row * cellw, 3), 14, dtype=np.uint8)
    colors = {0: (50, 50, 50), 10: (14, 14, 14),
              11: (170, 170, 170), 12: (250, 250, 250)}
    for i, g in enumerate(all_glyphs):
        ry, rx = divmod(i, per_row)
        y0 = ry * cellh + gap
        x0 = rx * cellw + gap
        for y in range(16):
            for x in range(g["w"]):
                v = int(g["mat"][y, x])
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = \
                    colors.get(v, (255, 0, 0))
    p = OUT / "ALL_GLYPHS_TRUE_WIDTH.png"
    save_png(p, img)
    print(f"\n✔ 完整字库图 {p}  ({img.shape[1]}x{img.shape[0]}, "
          f"{len(all_glyphs)} 字)")

    # ── 用完整字形（12 宽 = 96B）去 ROM 搜 ─────────────────
    print("\n" + "=" * 78)
    print("用「完整 12x16 字形」搜 ROM（这是此前从未试过的正确尺寸）")
    print("=" * 78)
    for wname in ("12", "10", "11"):
        gs = groups[wname]
        if not gs:
            continue
        pats = []
        for g in gs:
            body = b"".join(pack_row4(g["mat"][y], g["w"]) for y in range(16))
            pats.append(body)
        size = len(pats[0])
        hits = []
        for i, pat in enumerate(pats):
            idx = rom.find(pat)
            if idx >= 0:
                hits.append((i, idx))
        print(f"  宽 {wname}（{size}B/字）：{len(hits)}/{len(pats)} 命中")
        for i, idx in hits[:8]:
            print(f"    @0x{0x08000000 + idx:08X}  (字形#{i}, 宽{gs[i]['w']})")

    # ── 也试「去掉空行」「只存墨迹行」等变体 ──────────────
    print("\n  变体：只打包墨迹行 y=3..14（12 行）")
    for wname in ("12", "10"):
        gs = groups[wname]
        if not gs:
            continue
        pats = []
        for g in gs:
            body = b"".join(pack_row4(g["mat"][y], g["w"]) for y in range(3, 15))
            pats.append(body)
        hits = sum(1 for p in pats if rom.find(p) >= 0)
        print(f"    宽 {wname}（{len(pats[0])}B）：{hits}/{len(pats)}")

    # ── 每个字单独存一份，供后续比对 ──────────────────────
    meta = [{"row": g["row"], "x0": g["x0"], "w": g["w"]}
            for g in all_glyphs]
    (OUT / "glyphs.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    # 存原始矩阵
    np.save(OUT / "mats.npy",
            np.array([g["mat"] for g in all_glyphs], dtype=object),
            allow_pickle=True)
    print(f"\n已写 {OUT / 'glyphs.json'} 与 mats.npy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
