#!/usr/bin/env python3
"""fonts_extract.py — 1bpp 位流字库 → BDF 提取工具。

背景（2026-09-10 用户拍板）：现行汉字源是 pokeE 1bpp 位流
（流水线产物 `work/<GAME>/graphic/fonts/PokeRSFontChs{Big,Small}1Bpp_unshadow(...).bin`，
charmap 序 7168 槽；仓库根 graphic/fonts 镜像已于 2026-09-11 删除），
而 `fonts/default/*.bdf` 还是旧 4bpp 槽的导出转储。本工具把 1bpp 位流按
**渲染端真实几何**反写成 BDF，让 BDF 生成链（build_chinese_font.py）成为
与实机一致的字体源。

几何（必须与渲染端一致，否则重建后字形会平移）：
  text_translater.c: `CHS_1BPP_ROW_OFF_BIG=2` / `CHS_1BPP_ROW_OFF_SMALL=5`
  chinese_glyph.c   : 位流 `bits[r*width + x]`，MSB-first，行间无填充；
                      墨迹落 cell[y=row_off+r][x]（x=0 起）。
  ⇒ Big  11×11 @ row 2 → cell 行 [2,13)、列 [0,11)
     Small 9×9  @ row 5 → cell 行 [5,14)、列 [0,9)

输出 BDF 规格（= 历史 Normal.bdf / ttf_to_bdf.py 的 16px spec）：
  FONTBOUNDINGBOX 16 16 0 -2、FONT_ASCENT 14 / DESCENT 2、
  每字 BBX 16 16 0 -2、16 行 × 4 位 hex（低字节 = x8..15）。
  **不做 bbox 归一化** —— 落位忠实保留，配合 build_chinese_font.py
  的 `--ink-fixed` 可逐字节还原。

用法：
  python src/util/fonts_extract.py \
      --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt \
      --out-dir fonts/default
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from build_chinese_font import parse_charmap  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# 16px spec（= Normal/Small.bdf 头部约定）
SPEC_W, SPEC_H = 16, 16
SPEC_ASCENT, SPEC_DESCENT = 14, 2
TOP_PAD = 2  # 历史墨迹起始行

# 各槽 1bpp 源与几何（流水线产物位置；仓库根 graphic/fonts 已于 2026-09-11 删除）
GAME = "POKEMON_RUBY_AXVJ00"
SRC_DIR = ROOT / "work" / GAME / "graphic" / "fonts"
BIG_BIN = SRC_DIR / "PokeRSFontChsBig1Bpp_unshadow(0x1C000).bin"
SMALL_BIN = SRC_DIR / "PokeRSFontChsSmall1Bpp_unshadow(0x13400).bin"

SLOTS = {
    # label: (位流文件, 宽, 高, 落行, DWIDTH)
    "Normal": (BIG_BIN, 11, 11, 2, 12),
    "Small": (SMALL_BIN, 9, 9, 5, 10),
}


def unpack_1bpp(bits: bytes, width: int, rows: int) -> list[int]:
    """位流 → rows 个 int 行位图（bit0 = 最左列）。"""
    out: list[int] = []
    for r in range(rows):
        v = 0
        base = r * width
        for x in range(width):
            bi = base + x
            if bits[bi >> 3] >> (7 - (bi & 7)) & 1:
                v |= 1 << x
        out.append(v)
    return out


def rows_to_cell(rows: list[int], width: int, row_off: int) -> list[str]:
    """墨迹行 → 16×16 cell 的 16 行 4 位 hex。

    BDF 每行字节的 **MSB = 最左像素**、第二字节 = x8..15；
    而 unpack_1bpp 的 bit x = 第 x 列（bit0 = 最左）。两者必须显式对位，
    否则整字左右镜像。
    """
    hex_rows = ["0000"] * SPEC_H
    for r, bits in enumerate(rows):
        y = row_off + r
        if not (0 <= y < SPEC_H):
            continue
        b = [0, 0]
        for x in range(width):
            if bits >> x & 1:
                b[x >> 3] |= 0x80 >> (x & 7)
        hex_rows[y] = "%02X%02X" % (b[0], b[1])
    return hex_rows


def write_bdf(path: Path, glyphs: list[tuple[int, str, list[str]]],
              name: str, advance: int, comment: str) -> None:
    lines = [
        "STARTFONT 2.1",
        "FONT -Meowth-%s-Medium-R-Normal--%d-%d-75-75-C-%d-ISO10646-1"
        % (name, SPEC_H, SPEC_H * 10, advance * 10),
        "SIZE %d 75 75" % SPEC_H,
        "FONTBOUNDINGBOX %d %d 0 %d" % (SPEC_W, SPEC_H, -SPEC_DESCENT),
        "STARTPROPERTIES 5",
        "FONT_ASCENT %d" % SPEC_ASCENT,
        "FONT_DESCENT %d" % SPEC_DESCENT,
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE %d" % SPEC_H,
        'COMMENT "%s"' % comment,
        "ENDPROPERTIES",
        "CHARS %d" % len(glyphs),
    ]
    for enc, gname, hex_rows in glyphs:
        lines += [
            "STARTCHAR %s" % gname,
            "ENCODING %d" % enc,
            "SWIDTH %d 0" % (advance * 10),
            "DWIDTH %d 0" % advance,
            "BBX %d %d 0 %d" % (SPEC_W, SPEC_H, -SPEC_DESCENT),
            "BITMAP",
            *hex_rows,
            "ENDCHAR",
        ]
    lines.append("ENDFONT")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def extract(label: str, bin_path: Path, width: int, rows: int, row_off: int,
            advance: int, charmap: dict[int, str], out_dir: Path) -> None:
    data = bin_path.read_bytes()
    stride = (width * rows + 7) // 8
    slot_n = len(data) // stride
    glyphs: list[tuple[int, str, list[str]]] = []
    blank = 0
    for slot in range(slot_n):
        ch = charmap.get(slot)
        if ch is None:
            continue
        bits = data[slot * stride:(slot + 1) * stride]
        ink = unpack_1bpp(bits, width, rows)
        if not any(ink):
            blank += 1
        enc = ord(ch)
        glyphs.append((enc, "uni%04X" % enc, rows_to_cell(ink, width, row_off)))
    out = out_dir / ("%s.bdf" % label)
    write_bdf(
        out, glyphs, label, advance,
        "Extracted from %s by src/util/fonts_extract.py; "
        "ink %dx%d @row%d, no bbox normalization" % (bin_path.name, width, rows, row_off),
    )
    print(f"{label}: {len(glyphs)} glyphs (empty {blank}) <- {bin_path.name} "
          f"[{width}x{rows} @row{row_off}] -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="1bpp glyph bins -> BDF (16px spec)")
    ap.add_argument("--charmap", type=Path,
                    default=ROOT / "configs/POKEMON_RUBY_AXVJ00/charmap.txt")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "fonts/default")
    ap.add_argument("--only", nargs="*", default=None,
                    help="只提取指定槽（默认全提）")
    args = ap.parse_args()

    charmap = parse_charmap(args.charmap)
    print(f"charmap slots: {len(charmap)}")
    for label, (bin_path, w, h, row_off, adv) in SLOTS.items():
        if args.only and label not in args.only:
            continue
        if not bin_path.is_file():
            print(f"⚠ 缺少 {bin_path}")
            continue
        extract(label, bin_path, w, h, row_off, adv, charmap, args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
