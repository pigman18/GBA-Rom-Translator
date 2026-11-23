#!/usr/bin/env python3
"""从 Unifont（原生 16x16 点阵）生成 8x9 的 small.bdf。

为什么需要这个脚本
==================
`configs/<game>/fonts/small.bdf` 原来由 `gen_chs_bdfs.py` 从 **SimSun 12px
位图缩小**得到。SimSun 没有 9px 点阵档（实测 available_sizes 只有
6x12 / 7x12 / 7x14 / 8x14 / 8x16 / 9x17），把 12px 压到 8px 后笔画糊成一团：

    蛋:  .#######      ← 13 画挤进 8px，上下结构完全看不出
         .#.####
         .####
         #...#
         .######
         .######
         ...####
         ######.#

而 **Unifont 是原生 16x16 点阵**（不是缩放），笔画是设计师手工排的 1px 线，
结构清晰。整框降采样（OR，块内任一像素有墨迹即算墨迹）到 8x9 后：

    蛋:  .#######      ← 上「疋」下「虫」都能认出
         ..#.#..#
         ..#.###.
         .#######
         #...#...
         ..#####.
         ..#####.
         ..#.#.#.
         .#######

为什么用 OR 而不是面积投票
--------------------------
Unifont 笔画只有 1px 宽，15x15 压到 8x9 时落在 2x2 块里只占 25%。
任何阈值（实测 50% / 60%）都会把横竖笔画整条抹掉：
    「土」只剩左竖，字形散架。
OR 保证笔画连续，代价是笔画略粗 —— 8px 下这是可接受的权衡。

用法
====
    python scripts/font/unifont_to_small_bdf.py
    python scripts/font/unifont_to_small_bdf.py --out configs/.../small.bdf
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INK_W = 8
INK_H = 9
PAD_TOP = 6          # 必须与旧 small 字库一致（实测 y=6..14），否则多行互相压盖
SLOT = 16


def parse_bdf(path: Path) -> tuple[dict[int, list[bytearray]], int, int]:
    """返回 {encoding: [row_bytes...]}, ascent, descent。"""
    text = path.read_text("utf-8", errors="replace")
    ascent = 14
    descent = 2
    m = re.search(r"^FONT_ASCENT\s+(\d+)", text, re.MULTILINE)
    if m:
        ascent = int(m.group(1))
    m = re.search(r"^FONT_DESCENT\s+(\d+)", text, re.MULTILINE)
    if m:
        descent = int(m.group(1))

    glyphs: dict[int, list[bytearray]] = {}
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].startswith("STARTCHAR"):
            i += 1
            continue
        enc = -1
        rows: list[bytearray] = []
        i += 1
        while i < n and not lines[i].startswith("BITMAP"):
            if lines[i].startswith("ENCODING"):
                enc = int(lines[i].split()[1])
            i += 1
        i += 1
        while i < n and not lines[i].startswith("ENDCHAR"):
            h = lines[i].strip()
            if h:
                rows.append(bytearray(int(h[j : j + 2], 16) for j in range(0, len(h), 2)))
            i += 1
        if enc >= 0 and rows:
            glyphs[enc] = rows
        i += 1
    return glyphs, ascent, descent


def ink_bbox(rows: list[bytearray], w: int, h: int):
    """返回 (x0, y0, x1, y1) 半开区间，或 None。"""
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if x // 8 < len(rows[y]) and ((rows[y][x // 8] >> (7 - (x % 8))) & 1):
                minx = min(minx, x)
                maxx = max(maxx, x)
                miny = min(miny, y)
                maxy = max(maxy, y)
    if maxx < 0:
        return None
    return minx, miny, maxx + 1, maxy + 1


def downsample_or(rows: list[bytearray], w: int, h: int,
                  ow: int = INK_W, oh: int = INK_H) -> bytearray:
    """整框 OR 降采样到 ow x oh。"""
    bb = ink_bbox(rows, w, h)
    out = bytearray(ow * oh)
    if bb is None:
        return out
    x0, y0, x1, y1 = bb
    cw, ch = x1 - x0, y1 - y0
    for oy in range(oh):
        sy0 = (oy * ch) // oh
        sy1 = max(sy0 + 1, ((oy + 1) * ch) // oh)
        for ox in range(ow):
            sx0 = (ox * cw) // ow
            sx1 = max(sx0 + 1, ((ox + 1) * cw) // ow)
            hit = 0
            for sy in range(sy0, min(sy1, ch)):
                src_y = y0 + sy
                if src_y >= len(rows):
                    continue
                row = rows[src_y]
                for sx in range(sx0, min(sx1, cw)):
                    src_x = x0 + sx
                    if src_x // 8 < len(row) and ((row[src_x // 8] >> (7 - (src_x % 8))) & 1):
                        hit = 1
                        break
                if hit:
                    break
            out[oy * ow + ox] = hit
    return out


def make_slot(ink: bytearray, ow: int = INK_W, oh: int = INK_H,
              pad_top: int = PAD_TOP, shadow: bool = True) -> list[bytearray]:
    """8x9 ink → 16x16 槽（每行 2 字节 = 16 位）。"""
    slot = [[0] * SLOT for _ in range(SLOT)]
    for y in range(oh):
        sy = y + pad_top
        if not (0 <= sy < SLOT):
            continue
        for x in range(ow):
            if not ink[y * ow + x]:
                continue
            slot[sy][x] = 1
            if shadow:
                for dx, dy in ((1, 0), (0, 1), (1, 1)):
                    tx, ty = x + dx, sy + dy
                    if 0 <= tx < SLOT and 0 <= ty < SLOT and slot[ty][tx] == 0:
                        slot[ty][tx] = 2
    out: list[bytearray] = []
    for y in range(SLOT):
        row = bytearray(2)
        for x in range(SLOT):
            if slot[y][x] == 1:
                row[x // 8] |= 0x80 >> (x % 8)
        out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Unifont 16x16 → 8x9 small.bdf")
    ap.add_argument("--unifont", type=Path,
                    default=ROOT / "tools/fonts/unifont-16.0.04.bdf.gz")
    ap.add_argument("--charmap", type=Path,
                    default=ROOT / "configs/POKEMON_RUBY_AXVJ00/charmap.txt")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/small.bdf")
    ap.add_argument("--no-shadow", action="store_true",
                    help="不生成阴影层（默认生成，与旧 small 字库一致）")
    args = ap.parse_args()

    # 解压 Unifont
    src = args.unifont
    if src.suffix == ".gz":
        tmp = ROOT / "work/_unifont.bdf"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(src, "rb") as f:
            tmp.write_bytes(f.read())
        src = tmp

    print(f"读 Unifont: {src}")
    uni, _, _ = parse_bdf(src)
    print(f"  {len(uni)} 字形")

    # charmap：需要覆盖的字符集
    chars: list[str] = []
    pat = re.compile(r"^([0-9A-Fa-f]{2,4})=(.+)$")
    for line in args.charmap.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = pat.match(line)
        if m and len(m.group(2)) == 1:      # 只要单字符（charmap 里也有短语条目）
            chars.append(m.group(2))
    print(f"charmap: {len(chars)} 字符")

    # 生成
    out_lines = [
        "STARTFONT 2.1",
        "FONT -Meowth-Small-Medium-R-Normal--16-160-75-75-C-80-ISO10646-1",
        "SIZE 16 75 75",
        "FONTBOUNDINGBOX 16 16 0 -2",
        "STARTPROPERTIES 7",
        "FONT_ASCENT 14",
        "FONT_DESCENT 2",
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE 16",
        f'COMMENT "unifont_to_small_bdf.py: Unifont 16x16 → OR 降采样 {INK_W}x{INK_H}, '
        f'pad_top={PAD_TOP}"',
        "ENDPROPERTIES",
        f"CHARS {len(chars)}",
        "",
    ]
    miss = 0
    made = 0
    for ch in chars:
        enc = ord(ch)
        rows = uni.get(enc)
        if rows is None:
            miss += 1
            continue
        ink = downsample_or(rows, SLOT, SLOT)
        slot = make_slot(ink, shadow=not args.no_shadow)
        out_lines.append(f"STARTCHAR U+{enc:04X}")
        out_lines.append(f"ENCODING {enc}")
        out_lines.append("SWIDTH 80 0")
        out_lines.append(f"DWIDTH {INK_W} 0")
        out_lines.append("BBX 16 16 0 -2")
        out_lines.append(f'COMMENT "unifont@{INK_W}x{INK_H}"')
        out_lines.append("BITMAP")
        for r in slot:
            out_lines.append(r.hex().upper())
        out_lines.append("ENDCHAR")
        made += 1

    out_lines.append("ENDFONT")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"写入 {args.out}: {made} 字形（Unifont 缺 {miss}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
