#!/usr/bin/env python3
"""从「美版 Ruby 汉化版」ROM 导出 small（小字）字库 → BDF。

═══════════════════════════════════════════════════════════════════
一、字库位置（反汇编 + GDB + 实测）
═══════════════════════════════════════════════════════════════════
汉化版（work/_us_cn.gba）与美版（AXVE）字体表相同（0x081E6B48），
但中文字库是额外注入到扩展区 `0x09000000` 起的。

取字模代码（0x090000CC 反汇编）：
    0x090000CC: lsls r0, r0, #5        ← glyph*32，再 +32 取下半
    0x090000CE: ldr  r1, [r6, #0x24]   ← 字库基址（运行时 win 字段）
    0x090000D0: adds r1, r1, r0        ← *upper = base + glyph*32
    0x090000F0: adds r0, #32           ← *lower = *upper + 32

文本串里汉字编码 `F7 00 ll tt`，`0x057d` 就是字库序号 idx。
GDB 实测「多刺菊石兽」名字串：多=1405 刺=3791 菊=1425。

由 idx 反推：`0x090DB0A0 - 1405*128 = 0x090DB0A0`，
该基址解出的三个字字形正确 ⇒

    **字库基址 S = 0x090DB0A0，每字 128B**

═══════════════════════════════════════════════════════════════════
二、两套字库连续存放（实测字形高度分段）
═══════════════════════════════════════════════════════════════════
按 idx 采样字形墨迹的行范围，出现干净的两段：

    idx 0..1404   : 墨迹 row2..row12，**11 行高**  ← Normal 大字
    idx 1405..    : 墨迹 row6..row14，** 9 行高**  ← Small  小字

二分确认分界在 idx=1405（idx 1404 仍是 11 行，1405 起变 9 行）。
两段共用同一基址、同一 128B 步长，只是字形高度不同。

**本脚本默认只导 Small 段（idx >= 1405）。**

═══════════════════════════════════════════════════════════════════
三、128B 槽内排布（实测）
═══════════════════════════════════════════════════════════════════
128B = 4 个 8x8 4bpp tile（每 tile 32B）。实测一个字的 4 tile 墨量：

    tile0 = 11 ink   ← 字形上半 8x8
    tile1 = 34 ink   ← 字形下半 8x8
    tile2 =  1 ink   ← 几乎空
    tile3 =  0 ink   ← 空

⇒ 有效字形 = **tile0 + tile1 纵向拼接成 8x16**，tile2/3 是填充。

nibble 语义：0=背景 14=阴影 15=主墨，**lo nibble 是左像素**（与日版一致）。

═══════════════════════════════════════════════════════════════════
四、编码
═══════════════════════════════════════════════════════════════════
汉化版没有独立的 gidx→Unicode 表，`F7 00 ll tt` 里的 tt/ll 直接就是
字库 idx。本脚本先用 **ENCODING = 0xE000 + (idx - SMALL_BASE_IDX)** 的
私有区编码输出，保留 COMMENT 记录原始 idx，等映射表确认后再回填 Unicode。

用法
====
    python scripts/font/export/export_us_cn_small_bdf.py
    python scripts/font/export/export_us_cn_small_bdf.py --verify
    python scripts/font/export/export_us_cn_small_bdf.py --count 32
    python scripts/font/export/export_us_cn_small_bdf.py --all   # 连大字一起导
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# ---- 实测常量（来源见模块 docstring）
DEFAULT_ROM = ROOT / "work/_us_cn.gba"
FONT_BASE = 0x090DB0A0      # 两套字库共用基址
BYTES_PER_GLYPH = 128       # 每字 128B = 4 个 8x8 tile
TILE_BYTES = 32
GLYPH_W = 8
GLYPH_H = 16                # 有效字形 = tile0(8行) + tile1(8行)

SMALL_BASE_IDX = 1405       # 实测分界：<=1404 是 11 行大字，>=1405 是 9 行小字
FONT_END = 0x091B5FA0       # 实测非空范围上界

BG, SHADOW, INK = 0, 14, 15


def read_glyph(rom: bytes, idx: int) -> list[list[int]]:
    """取 idx 号字形 → 8x16 nibble 网格（lo nibble 为左像素）。"""
    base = FONT_BASE - 0x08000000 + idx * BYTES_PER_GLYPH
    if base < 0 or base + 64 > len(rom):
        return [[BG] * GLYPH_W for _ in range(GLYPH_H)]
    rows: list[list[int]] = []
    for tile in range(2):                      # 只取 tile0 / tile1
        off = base + tile * TILE_BYTES
        chunk = rom[off:off + TILE_BYTES]
        for y in range(8):
            rows.append([
                ((chunk[y * 4 + x // 2] & 0x0F) if x % 2 == 0
                 else (chunk[y * 4 + x // 2] >> 4))
                for x in range(GLYPH_W)
            ])
    return rows


def ink_rows(grid: list[list[int]]) -> list[int]:
    return [i for i, row in enumerate(grid) if any(v != BG for v in row)]


def ink_bbox(grid: list[list[int]]) -> tuple[int, int, int, int] | None:
    xs, ys = [], []
    for y, row in enumerate(grid):
        for x, v in enumerate(row):
            if v != BG:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def grid_to_bdf_rows(grid: list[list[int]], only_ink: bool = True) -> list[str]:
    """8x16 nibble 网格 → BDF 的 16 行十六进制（每行 8px，MSB 最左）。

    ★ 汉化版字库是**三色**：0=背景 / 14=阴影 / 15=主墨（实测 idx1405 的
      nibble 分布 {0:57, 14:26, 15:45}，没有中间灰度）。
    BDF 是 1bit 位图，只能二选一：
      only_ink=True  只算 15（主墨）—— 字形轮廓干净，但丢阴影
      only_ink=False 14 和 15 都算 —— 保留原版描边观感，笔画会显得更粗

    注意本项目的 small.bdf 反而带灰度抗锯齿（nibble 1..12 都有），
    与汉化版不是同一套字形来源，对比时别混为一谈。
    """
    out = []
    for y in range(GLYPH_H):
        bits = 0
        for x in range(GLYPH_W):
            v = grid[y][x]
            if (v == INK) if only_ink else (v != BG):
                bits |= 0x80 >> x
        out.append(f"{bits:02X}")
    return out


def emit_bdf(out_path: Path, glyphs: list[tuple[int, list[list[int]]]],
             ascent: int, descent: int,
             font_name: str = "USCN") -> None:
    """写 BDF。

    ★ XLFD 必须严格 15 字段（以 '-' 分隔、以 '-' 开头）。字段名内部**不能**
      再出现 '-'，否则字段被拆多、BdfEditor 等解析器直接打不开
      （实测：名字写成 "US-CN-Small-8x16" 会把 15 字段撑成 18）。
    ★ FONTBOUNDINGBOX 必须与每个字的 BBX 一致，否则部分解析器拒绝。
    ★ COMMENT 一律加双引号（与仓内 small.bdf 一致）。
    """
    lines = [
        "STARTFONT 2.1",
        # 15 字段：foundry family weight slant setwidth addstyle pixelsize
        #          pointsize resx resy spacing avgwidth registry encoding
        f"FONT -Meowth-{font_name}-Medium-R-Normal--16-160-75-75-C-80-ISO10646-1",
        "SIZE 16 75 75",
        "FONTBOUNDINGBOX 8 16 0 0",
        # ★ 属性区只放**规范定义的**原子属性。不放 COMMENT —— 部分解析器
        #   （BdfEditor / bdflib）在属性区遇到 COMMENT 会直接判格式错。
        "STARTPROPERTIES 3",
        f"FONT_ASCENT {ascent}",
        f"FONT_DESCENT {descent}",
        "DEFAULT_CHAR 0",
        "ENDPROPERTIES",
        f"CHARS {len(glyphs)}",
        "",
    ]
    for seq, (idx, grid) in enumerate(glyphs):
        rows = grid_to_bdf_rows(grid)
        # ★ ENCODING 必须 <= 0xFFFF：0xE000+idx 会超界（实测 idx 到 8410 时
        #   会算出 0x10xxx，BdfEditor 拒绝）。改用从 0xE100 起顺序编号，
        #   真实字库序号记在 COMMENT 里，映射脚本按顺序反查。
        enc = 0xE100 + seq
        lines.append(f"STARTCHAR us_cn_{idx:04X}")
        lines.append(f"ENCODING {enc}")
        lines.append("SWIDTH 500 0")
        lines.append("DWIDTH 8 0")
        lines.append("BBX 8 16 0 0")
        lines.append(f'COMMENT "font_idx={idx}"')
        lines.append("BITMAP")
        lines.extend(rows)
        lines.append("ENDCHAR")
        lines.append("")
    lines.append("ENDFONT")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def show(grid: list[list[int]]) -> list[str]:
    ch = {BG: ".", SHADOW: "+", INK: "#"}
    return ["".join(ch.get(v, "?") for v in row) for row in grid]


def main() -> int:
    ap = argparse.ArgumentParser(description="导出美版汉化版 small 字库 → BDF")
    ap.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/small_us_cn.bdf")
    ap.add_argument("--count", type=int, default=0, help="只导前 N 字（0=全部）")
    ap.add_argument("--all", action="store_true",
                    help="（已默认）连 Normal 大字段一起导")
    ap.add_argument("--big-only", action="store_true", help="只导大字段 idx<1405")
    ap.add_argument("--small-only", action="store_true", help="只导小字段 idx>=1405")
    ap.add_argument("--verify", action="store_true", help="打印样本字形")
    args = ap.parse_args()

    if not args.rom.is_file():
        raise SystemExit(f"error: ROM 不存在: {args.rom}")
    rom = args.rom.read_bytes()

    total = (FONT_END - FONT_BASE) // BYTES_PER_GLYPH
    # 实测两段字符完全无重叠（大字段 1113 字 / 小字段 5650 字），
    # 要完整字符集必须都导；--big-only / --small-only 可限定。
    if args.small_only:
        start, end = SMALL_BASE_IDX, total
    elif args.big_only:
        start, end = 0, SMALL_BASE_IDX
    else:
        start, end = 0, total
    n = min(args.count, end - start) if args.count > 0 else end - start
    print(f"字库基址 0x{FONT_BASE:08X}，共 {total} 字槽")
    print(f"  导出区间 idx {start}..{start + n - 1}"
          f"{'（含大字段）' if args.all else '（仅小字段）'}")

    glyphs: list[tuple[int, list[list[int]]]] = []
    blank = 0
    for idx in range(start, start + n):
        g = read_glyph(rom, idx)
        if not ink_rows(g):
            blank += 1
            continue
        glyphs.append((idx, g))

    # 小字段基线：墨迹 row6..14 ⇒ ascent = 14+1 行，descent 2 行
    emit_bdf(args.out, glyphs, ascent=15, descent=1)
    print(f"写入 {args.out}")
    print(f"  非空字形 {len(glyphs)} 个，跳过空白 {blank} 个")

    if args.verify:
        for idx, g in glyphs[:6]:
            bb = ink_bbox(g)
            print(f"\nidx {idx} (0x{idx:04X}) 墨迹行 {ink_rows(g)[0]}..{ink_rows(g)[-1]}"
                  f"  bbox={bb}")
            for i, line in enumerate(show(g)):
                print(f"   {i:2d} {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())