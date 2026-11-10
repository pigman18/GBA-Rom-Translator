#!/usr/bin/env python3
"""调研(180) 验证「汉字 = 8 宽 x 16 高 = 上下两个 8x8 tile 拼成」。

═══════════════════════════════════════════════════════════════════════════
【(179) 看图得到的决定性线索】
═══════════════════════════════════════════════════════════════════════════
(179) 把 tilemap 12 行当成 12 条独立文字行拼图，结果每个字都「上下错位、
各露半截」（例如「22:04」出现两次半截）。

⇒ 真实结构是：**一行文字占 tilemap 两行**，上排是字形的上半 (y0..7)，
  下排是下半 (y8..15)。**汉字是 8 宽 x 16 高**。

这与检查点里「墨迹 12 高」完全吻合（16 高格里 y=0..2 空、y=3..14 有墨、y=15 空）。

【本脚本验证三件事】
 V1 把「tilemap 行 r 的 tile T」与「行 r+1 的 tile T'」竖向拼接，
    是否得到完整可读汉字？
 V2 两行的 tile 序号关系（差多少？是否恒为 24 = 每行字数？）
 V3 竖向拼接后，字的左右是否完整（8 宽够不够装汉字）？
    —— 若左右被切，说明还要横向再拼一个 tile（即 16x16 = 4 tile）

【判定标准】
 拼出来能读成完整汉字（不缺失笔画）→ 8x16 成立，2 tile/字
 拼出来左右各缺一半       → 16x16 成立，4 tile/字

用法：python scripts/research/firered/180_verify_8x16.py
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "glyph180"
VRAM = 0x06000000
SCREEN_BASE = 0xF000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    o = SCREEN_BASE + (r * 32 + c) * 2
    return struct.unpack_from("<H", vr, o)[0]


def show(m: np.ndarray) -> list[str]:
    tbl = {0: ".", 10: " ", 11: "+", 12: "#"}
    return ["".join(tbl.get(int(v), "?") for v in row) for row in m]


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
    vr = (SNAP / "vram.bin").read_bytes()

    # ── V2：先看行间 tile 序号关系 ─────────────────────────
    print("=" * 78)
    print("V2 相邻 tilemap 行的 tile 序号关系")
    print("=" * 78)
    for r in (1, 2, 3, 4, 5):
        a = [entry(vr, r, c) & 0x3FF for c in range(3, 27)]
        b = [entry(vr, r + 1, c) & 0x3FF for c in range(3, 27)]
        pa = [(entry(vr, r, c) >> 12) & 0xF for c in range(3, 27)]
        pb = [(entry(vr, r + 1, c) >> 12) & 0xF for c in range(3, 27)]
        print(f"  行{r:>2} tile={a[:6]}... pal={set(pa)}")
        print(f"  行{r + 1:>2} tile={b[:6]}... pal={set(pb)}")
        print(f"       逐列差 = {[y - x for x, y in zip(a, b)][:10]}")
        print()

    # ── V1：竖向拼接 tilemap 两行 ──────────────────────────
    print("=" * 78)
    print("V1 把 tilemap 行 r(上) + 行 r+1(下) 竖向拼成 8x16")
    print("=" * 78)
    # 文字行从 tilemap 行 1 开始 ⇒ 配对必须是 (1,2),(3,4),(5,6)...
    # 之前按 range(0,19,2) 得到 (2,3),(4,5) 是错位的，拼出「上一行下半 + 下一行上半」。
    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    print(f"  tilemap 有文字的行：{text_rows}")
    if text_rows:
        print(f"  首行={text_rows[0]}  推断配对起点={text_rows[0]}")

    lines: list[dict] = []
    start = text_rows[0] if text_rows else 0
    for r in range(start, 19, 2):
        # 只处理「上排有文字」的
        tops = [entry(vr, r, c) for c in range(30)]
        if not any(((e >> 12) & 0xF) == 15 for e in tops):
            continue
        bots = [entry(vr, r + 1, c) for c in range(30)]
        # 找连续文字段
        segs = []
        cur = []
        for c in range(30):
            et = entry(vr, r, c)
            if ((et >> 12) & 0xF) == 15:
                cur.append(c)
            else:
                if cur:
                    segs.append(cur)
                    cur = []
        if cur:
            segs.append(cur)
        for cols in segs:
            lines.append({"row": r, "cols": cols})

    print(f"  找到 {len(lines)} 个文字段")
    for ln in lines[:4]:
        r, cols = ln["row"], ln["cols"]
        print(f"\n  ── tilemap 行 {r}+{r + 1}  列 {cols[0]}..{cols[-1]} "
              f"({len(cols)} 字) ──")
        # 拼 8 x 16
        canvas = np.full((16, len(cols) * 8), 10, dtype=np.uint8)
        for i, c in enumerate(cols):
            et = entry(vr, r, c)
            eb = entry(vr, r + 1, c)
            tt, tb = et & 0x3FF, eb & 0x3FF
            ot, ob = tt * 32, tb * 32
            if ot + 32 <= len(vr):
                canvas[0:8, i * 8:(i + 1) * 8] = tile_nibs(vr[ot:ot + 32])
            if ob + 32 <= len(vr):
                canvas[8:16, i * 8:(i + 1) * 8] = tile_nibs(vr[ob:ob + 32])
        for line in show(canvas):
            print(f"    {line}")

    # ── 输出大图（按 8x16 正确组合）────────────────────────
    print("\n" + "=" * 78)
    print("输出：按 8x16 正确组合的全屏字形图")
    print("=" * 78)
    SCALE = 3
    colors = {0: (60, 60, 60), 10: (16, 16, 16),
              11: (150, 150, 150), 12: (245, 245, 245)}

    maxw = max((len(ln["cols"]) for ln in lines), default=1)
    W = maxw * 8 * SCALE + 8
    H = len(lines) * 16 * SCALE + len(lines) * 4
    sheet = np.full((H, W, 3), 16, dtype=np.uint8)
    for li, ln in enumerate(lines):
        r, cols = ln["row"], ln["cols"]
        y0 = li * (16 * SCALE + 4)
        for i, c in enumerate(cols):
            et = entry(vr, r, c)
            eb = entry(vr, r + 1, c)
            for half, e in ((0, et), (1, eb)):
                t = e & 0x3FF
                o = t * 32
                if o + 32 > len(vr):
                    continue
                m = tile_nibs(vr[o:o + 32])
                for y in range(8):
                    for x in range(8):
                        py = y0 + (half * 8 + y) * SCALE
                        px = 4 + (i * 8 + x) * SCALE
                        sheet[py:py + SCALE, px:px + SCALE] = colors.get(
                            int(m[y, x]), (255, 0, 0))
    p = OUT / "TEXT_8x16.png"
    save_png(p, sheet)
    print(f"  ✔ {p}  ({sheet.shape[1]}x{sheet.shape[0]})")

    (OUT / "lines.json").write_text(
        json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✔ {OUT / 'lines.json'}  ({len(lines)} 段)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
