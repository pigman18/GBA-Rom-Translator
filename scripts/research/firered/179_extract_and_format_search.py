#!/usr/bin/env python3
"""调研(179) 提取 VRAM 里全部真实字形，输出成图 + 数据，并做格式穷举找 ROM 源。

═══════════════════════════════════════════════════════════════════════════
【本轮已确证的事实（176/177）】
═══════════════════════════════════════════════════════════════════════════
F1 tilemap(0xF000) 中 pal=15 文字项，相邻项 tile 序号差 **100% = +1**
   ⇒ 整行文字在 charBase 里是连续 tile 序列，无跨 tile 拼字。
F2 汉字 = **1 个 8x8 4bpp tile = 32 字节**（检查点里「13px 变宽」旧结论作废）
F3 VRAM 含笔画的 tile 共 **103 个**（tilemap 引用 288 个，其余为空）
F4 中文首行字 = 0x06000020 起（tile 1..7）
F5 空间账重算：2299 字 x 32B = 73,568 B，远小于可用 ~30 万字节

【本脚本做两件事】
 A. 提取：把 103 个字形按「在屏幕上的真实位置」重排成一张直观大图
    （用户要的「一大张字库 PNG」——这次是真实的、由 tilemap 反推的）
 B. 穷举：把每个字形规范化成多种二进制格式候选，去 ROM 全量搜
      F-a 4bpp 原样 32B                F-b 4bpp nibble 高低互换
      F-c 1bpp 墨迹 8B（12→1）         F-d 1bpp 墨迹 8B（11或12→1）
      F-e 2bpp 8B                      F-f 1bpp 8B 行列转置
      F-g 1bpp 8B 每行位序反转          F-h 1bpp 8B 整字节位反转
   任一格式命中 ≥8 个字 → 找到字库。

【为什么要重做穷举】
之前所有搜索（检查点「已排除的字形来源」）都是基于「字是 13px 变宽 / 16x16」
的假设做的（32B 4bpp 完整匹配、16x16 1bpp 等）。
现在确认是 **8x8 单 tile**，所以 1bpp 只有 **8 字节**，2bpp 只有 16 字节——
**这些尺寸之前从没搜过**。这是全新的搜索空间。

用法：python scripts/research/firered/179_extract_and_format_search.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "glyph179"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

VRAM = 0x06000000
SCREEN_BASE = 0xF000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def rows_to_bytes(rows: np.ndarray) -> bytes:
    """8x8 0/1/2/3 值矩阵 → 每行 2 bit x 8 = 16 bit = 2 字节，共 16 字节。"""
    out = bytearray()
    for y in range(8):
        v = 0
        for x in range(8):
            v |= (int(rows[y, x]) & 3) << (14 - x * 2)
        out += v.to_bytes(2, "big")
    return bytes(out)


def pack_1bpp(rows01: np.ndarray, *, msb_first: bool = True,
              transpose: bool = False) -> bytes:
    """8x8 0/1 → 每行 1 字节，共 8 字节。"""
    m = rows01.T if transpose else rows01
    out = bytearray()
    for y in range(8):
        v = 0
        for x in range(8):
            if m[y, x]:
                bit = (7 - x) if msb_first else x
                v |= 1 << bit
        out.append(v)
    return bytes(out)


def bitrev(b: int) -> int:
    r = 0
    for i in range(8):
        if b & (1 << i):
            r |= 1 << (7 - i)
    return r


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()

    # ── A. 从 tilemap 反推屏幕布局，提取真实字形 ──────────────
    print("=" * 78)
    print("A. 从 tilemap 反推屏幕文字布局")
    print("=" * 78)

    glyphs: dict[int, np.ndarray] = {}
    for t in range(0, 1200):
        off = t * 32
        if off + 32 > len(vr):
            break
        m = tile_nibs(vr[off:off + 32])
        if int(np.sum(m == 12)) + int(np.sum(m == 11)) > 0:
            glyphs[t] = m
    print(f"  含笔画 tile：{len(glyphs)} 个  序号={sorted(glyphs)[:12]}...")

    # 屏幕逐行：把 tilemap 的每一项换成对应字形
    lines: list[tuple[int, list[int]]] = []
    for r in range(20):
        row = []
        for c in range(30):
            e = int.from_bytes(vr[SCREEN_BASE + (r * 32 + c) * 2:
                                 SCREEN_BASE + (r * 32 + c) * 2 + 2], "little")
            row.append((e & 0x3FF) if ((e >> 12) & 0xF) == 15 else -1)
        if any(t >= 0 for t in row):
            lines.append((r, row))
    print(f"  有文字的行：{[r for r, _ in lines]}")

    # 每个「连续 tile 段」= 一行字符串
    segs: list[dict] = []
    for r, row in lines:
        cur = []
        for c, t in enumerate(row):
            if t < 0:
                if cur:
                    segs.append({"row": r, "col0": cur[0][0], "tiles": [x[1] for x in cur]})
                    cur = []
                continue
            cur.append((c, t))
        if cur:
            segs.append({"row": r, "col0": cur[0][0], "tiles": [x[1] for x in cur]})
    print(f"  文字段（连续串）：{len(segs)} 段")
    for s in segs:
        print(f"    行{s['row']:>2} 列{s['col0']:>2}  {len(s['tiles'])} 字  tile={s['tiles']}")

    # 拼大图：每段一行
    SCALE = 3
    pad = 2
    W = max((len(s["tiles"]) for s in segs), default=1) * (8 + pad)
    H = len(segs) * (8 + pad)
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    canvas[:, :] = 16  # 深底

    colors = {0: (60, 60, 60), 10: (16, 16, 16), 11: (150, 150, 150), 12: (245, 245, 245)}

    for si, s in enumerate(segs):
        for ti, t in enumerate(s["tiles"]):
            m = glyphs.get(t)
            if m is None:
                continue
            y0 = si * (8 + pad)
            x0 = ti * (8 + pad)
            for y in range(8):
                for x in range(8):
                    canvas[y0 + y, x0 + x] = colors.get(int(m[y, x]), (255, 0, 0))

    big = np.repeat(np.repeat(canvas, SCALE, axis=0), SCALE, axis=1)
    p = OUT / "VRAM_GLYPHS_TRUE.png"
    save_png(p, big)
    print(f"\n  ✔ 已输出 {p}  ({big.shape[1]}x{big.shape[0]})")

    # 另存一张：所有含笔画 tile 平铺（不管屏幕位置）
    tl = sorted(glyphs)
    cols = 20
    rows = (len(tl) + cols - 1) // cols
    cw, chh = 8 * SCALE + 2, 8 * SCALE + 2
    sheet = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
    for i, t in enumerate(tl):
        m = glyphs[t]
        ry, rx = divmod(i, cols)
        for y in range(8):
            for x in range(8):
                sheet[ry * chh + y * SCALE:ry * chh + (y + 1) * SCALE,
                      rx * cw + x * SCALE:rx * cw + (x + 1) * SCALE] = \
                    colors.get(int(m[y, x]), (255, 0, 0))
    p2 = OUT / "VRAM_ALL_TILES.png"
    save_png(p2, sheet)
    print(f"  ✔ 已输出 {p2}  ({sheet.shape[1]}x{sheet.shape[0]}, {len(tl)} tiles)")

    # ── B. 格式穷举搜 ROM ─────────────────────────────────
    print("\n" + "=" * 78)
    print("B. 格式穷举：8x8 单 tile 的各种二进制形态 → 全 ROM 搜索")
    print("=" * 78)

    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()
    print(f"  ROM(汉化) {len(rom):,} B    ROM(原版) {len(rom_or):,} B")

    # 只挑「墨量适中」的字形做种子（避免全空/全满的假信号）
    seeds = []
    for t in tl:
        m = glyphs[t]
        ink = int(np.sum(m == 12)) + int(np.sum(m == 11))
        if 4 <= ink <= 50:
            seeds.append((t, m))
    print(f"  种子字形（4<=墨量<=50）：{len(seeds)} 个")

    binar = {
        "ink12": lambda m: (m == 12).astype(np.uint8),
        "ink1112": lambda m: ((m == 11) | (m == 12)).astype(np.uint8),
        "ink12_core": lambda m: (m == 12).astype(np.uint8),
    }

    results: list[dict] = []
    for bname, bfn in binar.items():
        ones = np.zeros((len(seeds), 8, 8), dtype=np.uint8)
        for i, (t, m) in enumerate(seeds):
            ones[i] = bfn(m)
        for msb in (True, False):
            for trans in (False, True):
                pats = [pack_1bpp(ones[i], msb_first=msb, transpose=trans)
                        for i in range(len(seeds))]
                for brevv in (False, True):
                    pp = [bytes(bitrev(b) for b in x) if brevv else x for x in pats]
                    hits = 0
                    where = []
                    for i, pat in enumerate(pp):
                        idx = rom.find(pat)
                        if idx >= 0:
                            hits += 1
                            where.append(idx)
                    if hits >= 3:
                        results.append({"fmt": f"1bpp/{bname}/msb={msb}/trans={trans}/bitrev={brevv}",
                                        "hits": hits, "of": len(seeds),
                                        "offsets": where[:8]})
                        print(f"  1bpp {bname:<10} msb={msb!s:<5} trans={trans!s:<5} "
                              f"bitrev={brevv!s:<5} → {hits}/{len(seeds)} 命中")

    # 2bpp（16B）与 4bpp（32B）原样
    print("\n  2bpp / 4bpp 原样搜索：")
    for tag, sz_fn in (("2bpp16", lambda m: rows_to_bytes(m)),
                       ("4bpp32", None)):
        hits = 0
        for t, m in seeds:
            if sz_fn is None:
                pat = vr[t * 32:t * 32 + 32]
            else:
                pat = sz_fn(m)
            if rom.find(pat) >= 0:
                hits += 1
        print(f"    {tag}: {hits}/{len(seeds)}")

    if not results:
        print("\n  ✘ 所有 1bpp 格式组合均无 ≥3 命中")
    else:
        results.sort(key=lambda d: -d["hits"])
        print(f"\n  最佳：{results[0]['fmt']}  {results[0]['hits']}/{results[0]['of']}")

    (OUT / "search.json").write_text(
        json.dumps({"segs": segs, "glyph_tiles": tl, "results": results},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'search.json'}")
    return 0


def save_png(path: Path, arr: np.ndarray) -> None:
    """不依赖 PIL：手写 PNG。"""
    import struct
    import zlib
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


if __name__ == "__main__":
    raise SystemExit(main())
