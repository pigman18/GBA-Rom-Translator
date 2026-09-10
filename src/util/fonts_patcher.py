#!/usr/bin/env python3
"""fonts_patcher.py — Middle 窄体字库派生工具（分组 OR 重采样）。

从源 BDF 的墨迹按「分组 OR 横向重采样」派生 Middle.bdf，供
build_chinese_font.py 构建字库 bin。**不做 bbox 归一化**：源墨迹在 cell 内的
绝对落位原样保留（配合 build_chinese_font.py 的 --ink-fixed 可逐字节还原）。

重采样算法（2026-09-07 用户拍板，对比隔列抽稀/最近邻/寒蝉拉伸后选定）：
- 不丢笔画：输出第 X 列 = 源第 [X*SRC/DST, (X+1)*SRC/DST) 列的 OR；
- 相邻两笔落入同一输出列时并成一粗笔，字形保持可读；
- 行不重采样：源墨迹行数 INK_H 原样保留。

两代参数：
  旧（2026-09-07）：Normal 12 列 → Middle 8 列，墨 12 行 @row2  —— 默认值
  新（2026-09-10）：Normal 11 列 → Middle 9 列，墨 11 行 @row2
                    （--src-cols 11 --dst-cols 9 --ink-h 11）

备用 BDF：2026-09-10 起**无默认**（旧的 Middle_fallback.bdf 已随冗余 BDF 清理
删除）。新 Normal.bdf 覆盖全部 6807 个 charmap 字符，不再需要补字。

输出 BDF 规格与 Normal/Small.bdf 一致：FONTBOUNDINGBOX 16 16 0 -2、
FONT_ASCENT 14 / FONT_DESCENT 2、每字 BBX 16 16 0 -2、16 行 × 4 hex
（高字节 = x0..7，低字节 = x8..15，MSB = 最左）。

用法：
  python src/util/fonts_patcher.py \
      --source fonts/default/Normal.bdf \
      --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt \
      --out fonts/default/Middle.bdf \
      --src-cols 11 --dst-cols 9 --ink-h 11 --no-fallback
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


def parse_bdf_glyphs(path: Path) -> dict[int, list[int]]:
    """极简 BDF 解析：{encoding: [16 行位图，每行一个 int（bit15 = x0）]}。"""
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


def or_resample(rows: list[int], *, src_cols: int, dst_cols: int,
                ink_h: int, top_pad: int) -> list[int]:
    """16×16 行位图 → 墨迹 [top_pad, top_pad+ink_h) 行、src_cols→dst_cols 分组 OR。

    返回 dst_cols 宽的行位图，仍按「bit(15-X) = 第 X 列」约定（X=0 为最左）。
    """
    out: list[int] = []
    for y in range(ink_h):
        src = rows[top_pad + y] if top_pad + y < len(rows) else 0
        v = 0
        for X in range(dst_cols):
            a = X * src_cols // dst_cols
            b = max((X + 1) * src_cols // dst_cols, a + 1)
            mask = 0
            for x in range(a, min(b, src_cols)):
                mask |= 0x8000 >> x
            if src & mask:
                v |= 0x8000 >> X
        out.append(v)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="source BDF -> Middle.bdf (group-OR horizontal resample)"
    )
    ap.add_argument("--source", type=Path, default=Path("fonts/default/Normal.bdf"))
    ap.add_argument("--fallback-bdf", type=Path, default=None,
                    help="源字库缺字时取墨的备用 BDF（可选；不传则缺字留空。"
                         "2026-09-10 起默认无备用——旧的 fonts/default/Middle_fallback.bdf "
                         "已随冗余 BDF 清理删除，且新 Normal.bdf 覆盖全部 6807 个 charmap 字符）")
    ap.add_argument("--no-fallback", action="store_true",
                    help="显式禁用备用 BDF（源已全覆盖时用；不同几何的备用库会错位）")
    ap.add_argument("--charmap", type=Path,
                    default=Path("configs/POKEMON_RUBY_AXVJ00/charmap.txt"))
    ap.add_argument("--out", type=Path, default=Path("fonts/default/Middle.bdf"))
    ap.add_argument("--src-cols", type=int, default=12, help="源墨迹列数（旧 12 / 新 11）")
    ap.add_argument("--dst-cols", type=int, default=8, help="目标墨迹列数（旧 8 / 新 9）")
    ap.add_argument("--ink-h", type=int, default=12, help="墨迹行数（旧 12 / 新 11）")
    ap.add_argument("--top-pad", type=int, default=2, help="墨迹起始行")
    ap.add_argument("--advance", type=int, default=10, help="DWIDTH")
    args = ap.parse_args()

    src = parse_bdf_glyphs(args.source)
    print(f"source {args.source}: {len(src)} glyphs")
    fallback: dict[int, list[int]] = {}
    if not args.no_fallback and args.fallback_bdf and args.fallback_bdf.exists():
        fallback = parse_bdf_glyphs(args.fallback_bdf)
        if fallback:
            print(f"fallback {args.fallback_bdf}: {len(fallback)} glyphs")
    charmap = parse_charmap(args.charmap)
    chars = sorted({ch for val in charmap.values() for ch in val})
    print(f"charmap unique chars: {len(chars)}")
    print(f"resample: {args.src_cols} -> {args.dst_cols} cols, ink {args.ink_h} rows "
          f"@row{args.top_pad}")

    missing: list[str] = []
    empty_src = 0
    lines = [
        "STARTFONT 2.1",
        "FONT -Middle-Medium-R-Normal--%d-%d-75-75-P-%d-ISO10646-1"
        % (SPEC_H, SPEC_H * 10, args.advance * 10),
        "SIZE %d 75 75" % SPEC_H,
        "FONTBOUNDINGBOX %d %d 0 %d" % (SPEC_W, SPEC_H, -SPEC_DESCENT),
        "STARTPROPERTIES 5",
        "FONT_ASCENT %d" % SPEC_ASCENT,
        "FONT_DESCENT %d" % SPEC_DESCENT,
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE %d" % SPEC_H,
        'COMMENT "Derived from %s by src/util/fonts_patcher.py; group-OR %d->%d cols, '
        'ink %dx%d @row%d, no bbox normalization"'
        % (args.source.name, args.src_cols, args.dst_cols,
           args.dst_cols, args.ink_h, args.top_pad),
        "ENDPROPERTIES",
        "CHARS %d" % len(chars),
    ]
    for ch in chars:
        enc = ord(ch)
        if enc in src:
            ink = or_resample(src[enc], src_cols=args.src_cols, dst_cols=args.dst_cols,
                              ink_h=args.ink_h, top_pad=args.top_pad)
        elif enc in fallback:
            rows = fallback[enc]
            ink = [
                (rows[args.top_pad + y] & 0xFFFF) & ~((1 << (16 - args.dst_cols)) - 1)
                if args.top_pad + y < len(rows) else 0
                for y in range(args.ink_h)
            ]
        else:
            missing.append(ch)
            ink = [0] * args.ink_h
        if not any(ink):
            empty_src += 1
        hex_rows = ["0000"] * SPEC_H
        for y, v in enumerate(ink):
            y2 = args.top_pad + y
            if 0 <= y2 < SPEC_H:
                hex_rows[y2] = "%02X%02X" % ((v >> 8) & 0xFF, v & 0xFF)
        lines += [
            "STARTCHAR uni%04X" % enc,
            "ENCODING %d" % enc,
            "SWIDTH %d 0" % (args.advance * 10),
            "DWIDTH %d 0" % args.advance,
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
