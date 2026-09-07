#!/usr/bin/env python3
"""fonts_patcher.py — Middle 窄体字库派生工具。

从 Normal.bdf（12px 墨、16px spec）按「分组 OR 横向缩放」派生 Middle.bdf
（8px 窄墨、16px spec），供 build_chinese_font.py --narrow-8x12 构建字库 bin。

派生算法（2026-09-07 用户拍板，对比隔列抽稀/最近邻/寒蝉拉伸/fusion10 抽稀后选定）：
- 不丢笔画：输出第 X 列 = 源第 [3X/2, 3(X+1)/2) 列的 OR（12 列 → 8 列，1.5:1）；
- 相邻两笔落入同一输出列时并成一粗笔，全部字形保持可读（道/路/宝/梦/清/晰 实测）；
- 行不缩放：12 行墨原样保留（Middle 绘制 cell = 8×12，每字 2 tile）。

BDF 规格与 Normal/Small.bdf 一致：FONTBOUNDINGBOX 16 16 0 -2、
FONT_ASCENT 14 / FONT_DESCENT 2、每字 BBX 16 16 0 -2、16 行 × 4 hex；
墨迹放 x=0..7、y=TOP_PAD(2)..13（bbox 归一化构建链对绝对行位置不敏感，
此处仅保证 BDF 查看器里观感正确）。

用法：
  python src/util/fonts_patcher.py \
      --source fonts/default/Normal.bdf \
      --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt \
      --out fonts/default/Middle.bdf
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 复用构建链的 charmap 解析（单一事实源）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from build_chinese_font import parse_charmap  # noqa: E402

# 16px spec（= Normal/Small.bdf 的头部约定）
SPEC_W, SPEC_H = 16, 16
SPEC_ASCENT, SPEC_DESCENT = 14, 2
TOP_PAD = 2          # 墨迹起始行
INK_H = 12           # 墨迹行数（12px 行网格）
SRC_COLS, DST_COLS = 12, 8   # 12 → 8，1.5:1 分组 OR


def parse_bdf_glyphs(path: Path) -> dict[int, list[int]]:
    """极简 BDF 解析：{encoding: [16 行位图，每行一个 int（bit15=x0）]}。"""
    text = path.read_text("utf-8", errors="replace")
    glyphs: dict[int, list[int]] = {}
    for m in re.finditer(
        r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
        text,
        re.MULTILINE | re.DOTALL,
    ):
        enc = int(m.group(1))
        rows: list[int] = []
        for line in m.group(2).strip().splitlines():
            if not line.strip():
                continue
            v = 0
            for byte in bytes.fromhex(line.strip()):
                v = (v << 8) | byte
            rows.append(v)
        glyphs[enc] = rows
    return glyphs


def or_squeeze(rows: list[int]) -> list[int]:
    """16×16 行位图 → 墨迹 [TOP_PAD, TOP_PAD+INK_H) 行、12→8 列分组 OR。"""
    out: list[int] = []
    for y in range(INK_H):
        src = rows[TOP_PAD + y] if TOP_PAD + y < len(rows) else 0
        v = 0
        for X in range(DST_COLS):
            a = X * SRC_COLS // DST_COLS
            b = max((X + 1) * SRC_COLS // DST_COLS, a + 1)
            mask = 0
            for x in range(a, min(b, SRC_COLS)):
                mask |= 0x8000 >> x
            if src & mask:
                v |= 0x80 >> X  # 输出位图：bit7 = x0（窄墨占左 8 列）
        out.append(v)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Normal.bdf → Middle.bdf (OR-squeeze 12→8)")
    ap.add_argument("--source", type=Path, default=Path("fonts/default/Normal.bdf"))
    ap.add_argument("--fallback-bdf", type=Path, default=Path("fonts/default/Middle_fallback.bdf"),
                    help="源字库缺字时取墨的备用 BDF（寒蝉窄体，覆盖符号类字符）")
    ap.add_argument("--charmap", type=Path,
                    default=Path("configs/POKEMON_RUBY_AXVJ00/charmap.txt"))
    ap.add_argument("--out", type=Path, default=Path("fonts/default/Middle.bdf"))
    args = ap.parse_args()

    src = parse_bdf_glyphs(args.source)
    print(f"source {args.source}: {len(src)} glyphs")
    fallback = parse_bdf_glyphs(args.fallback_bdf) if args.fallback_bdf.exists() else {}
    if fallback:
        print(f"fallback {args.fallback_bdf}: {len(fallback)} glyphs")
    charmap = parse_charmap(args.charmap)
    # 值可能是多码位字符串（复合字符），拍平成单字符集合
    chars = sorted({ch for val in charmap.values() for ch in val})
    print(f"charmap unique chars: {len(chars)}")

    missing: list[str] = []
    empty_src = 0
    lines = [
        "STARTFONT 2.1",
        "FONT -Middle-Medium-R-Normal--%d-%d-75-75-P-40-ISO10646-1"
        % (SPEC_H, SPEC_H * 10),
        "SIZE %d 75 75" % SPEC_H,
        "FONTBOUNDINGBOX %d %d 0 %d" % (SPEC_W, SPEC_H, -SPEC_DESCENT),
        "STARTPROPERTIES 5",
        "FONT_ASCENT %d" % SPEC_ASCENT,
        "FONT_DESCENT %d" % SPEC_DESCENT,
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE %d" % SPEC_H,
        'COMMENT "Derived from %s by src/util/fonts_patcher.py; OR-squeeze 12->8 cols"'
        % args.source.name,
        "ENDPROPERTIES",
        "CHARS %d" % len(chars),
    ]
    for ch in chars:
        enc = ord(ch)
        if enc in src:
            squeezed = or_squeeze(src[enc])
        elif enc in fallback:
            # 缺字回退：直接取备用 BDF 的墨迹行（同为 16px spec、窄墨在左 8 列）
            rows = fallback[enc]
            squeezed = [(rows[TOP_PAD + y] >> 8) & 0xFF
                        if TOP_PAD + y < len(rows) else 0
                        for y in range(INK_H)]
        else:
            missing.append(ch)
            squeezed = [0] * INK_H
        if not any(squeezed):
            empty_src += 1
        hex_rows = ["0000"] * SPEC_H
        for y, v in enumerate(squeezed):
            hex_rows[TOP_PAD + y] = "%02X00" % v
        lines += [
            "STARTCHAR uni%04X" % enc,
            "ENCODING %d" % enc,
            "SWIDTH 100 0",
            "DWIDTH 10 0",
            "BBX %d %d 0 %d" % (SPEC_W, SPEC_H, -SPEC_DESCENT),
            "BITMAP",
            *hex_rows,
            "ENDCHAR",
        ]
    lines.append("ENDFONT")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"written {len(chars)} glyphs -> {args.out}")
    if missing:
        print(f"⚠ 源字库缺字(空槽) {len(missing)} 字: "
              + "".join(missing[:60]) + ("..." if len(missing) > 60 else ""))
    print(f"空墨迹字形: {empty_src}")


if __name__ == "__main__":
    main()
