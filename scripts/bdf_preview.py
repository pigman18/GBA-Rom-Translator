#!/usr/bin/env python3
"""BDF 字形预览：把 BDF 里的点阵渲成 PNG 网格，用来肉眼验字。

为什么要这个工具
----------------
点阵字体的问题（断笔、缺偏旁、糊成一团、伪横）在代码里看不出来，
只能整屏看。以前每次改完都要「打包 ROM → 起模拟器 → 截图」，一轮几分钟；
这个脚本直接从 BDF 出图，秒级看到全部字形。

用法
----
  # 全部字形（自动分页，每页 cols×rows 个）
  python scripts/bdf_preview.py configs/POKEMON_RUBY_AXVJ00/fonts/normal.bdf \
      -o work/font_preview/normal.png

  # 只看指定字，放大看清楚笔画
  python scripts/bdf_preview.py <bdf> --text "烧伤药活力碎片先制之爪" \
      -o work/font_preview/check.png --scale 10

  # 只看第 2 页
  python scripts/bdf_preview.py <bdf> -o out.png --page 1

输出
----
默认每格 16×16（BDF 槽尺寸），放大 --scale 倍；格子上方留 12px 写码位，
同页顶部写「页码/总页数 + 字形数」。多页时文件名自动加 -p0/-p1…
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

SLOT = 16
LABEL_H = 12


def parse_bdf(path: Path) -> tuple[dict[int, dict], dict]:
    """返回 ({codepoint: {bbx, rows}}, font_meta)。"""
    glyphs: dict[int, dict] = {}
    meta: dict[str, str] = {}
    cur: dict | None = None
    in_bitmap = False

    for raw in path.read_text(encoding="latin-1").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("FONTBOUNDINGBOX"):
            meta["bbox"] = line
        elif line.startswith("CHARS "):
            meta["chars"] = line.split()[1]
        elif line.startswith("COMMENT") and "gen_" in line:
            meta["comment"] = line
        elif line.startswith("STARTCHAR"):
            cur = {"name": line.split(maxsplit=1)[1] if " " in line else "", "enc": None,
                   "bbx": (SLOT, SLOT, 0, 0), "rows": []}
        elif cur is None:
            continue
        elif line.startswith("ENCODING"):
            cur["enc"] = int(line.split()[1])
        elif line.startswith("BBX"):
            w, h, xo, yo = (int(v) for v in line.split()[1:5])
            cur["bbx"] = (w, h, xo, yo)
        elif line == "BITMAP":
            in_bitmap = True
        elif line == "ENDCHAR":
            in_bitmap = False
            if cur is not None and cur["enc"] is not None and cur["enc"] >= 0:
                glyphs[cur["enc"]] = cur
            cur = None
        elif in_bitmap and cur is not None:
            cur["rows"].append(line)
    return glyphs, meta


def glyph_to_image(g: dict) -> Image.Image:
    w, h, xo, yo = g["bbx"]
    img = Image.new("L", (SLOT, SLOT), 255)
    px = img.load()
    rowbytes = (w + 7) // 8
    for ry, hexline in enumerate(g["rows"]):
        if ry >= h:
            break
        try:
            data = bytes.fromhex(hexline)
        except ValueError:
            continue
        for x in range(w):
            if x >> 3 >= len(data):
                break
            if data[x >> 3] & (0x80 >> (x & 7)):
                gx = x + xo
                # BITMAP 行自上而下；整槽 BBX(h==SLOT) 时 ry 就是目标行，
                # 非整槽则按底边对齐（BDF 的 yoff 是相对基线的）。
                gy = ry if h == SLOT else ry + max(0, SLOT - h)
                if 0 <= gx < SLOT and 0 <= gy < SLOT:
                    px[gx, gy] = 0
    return img


def build_page(
    items: list[tuple[int, dict]],
    *,
    cols: int,
    scale: int,
    compact: bool = False,
    fg: tuple[int, int, int] = (250, 250, 250),
    bg: tuple[int, int, int] = (30, 30, 30),
    shadow: tuple[int, int, int] | None = (90, 90, 90),
) -> Image.Image:
    """compact=True 时输出「整版字形图」：无网格、无标注、深底白字带阴影，
    和 work/_probe/font_final/FONT_ALL.png 同风格 —— 这种图能一眼扫出断笔、
    缺偏旁、糊成一团的字，比逐页看格子有效得多。"""
    rows = (len(items) + cols - 1) // cols
    cw = SLOT * scale
    ch = cw if compact else (SLOT + LABEL_H) * scale
    img = Image.new("RGB", (max(cols * cw, 1), max(rows * ch, 1)), bg)
    px = img.load()

    # 先把所有墨点收集成一张大位图，再统一上色：阴影必须画在字下面，
    # 但只能画「字的右下 1px」，所以按 (x+1,y+1) 铺 shadow、再铺 fg。
    inkmap = Image.new("L", img.size, 0)   # 255 = 有墨
    ink = inkmap.load()

    for i, (cp, g) in enumerate(items):
        r, c = divmod(i, cols)
        cell = glyph_to_image(g)
        x0 = c * cw
        y0 = r * ch
        for y in range(SLOT):
            for x in range(SLOT):
                if cell.getpixel((x, y)) < 128:
                    for dy in range(scale):
                        for dx in range(scale):
                            ix = x0 + x * scale + dx
                            iy = y0 + y * scale + dy
                            if 0 <= ix < img.width and 0 <= iy < img.height:
                                ink[ix, iy] = 255

    if shadow is not None:
        off = scale if scale > 1 else 1
        for y in range(img.height):
            for x in range(img.width):
                if ink[x, y]:
                    sx, sy = x + off, y + off
                    if 0 <= sx < img.width and 0 <= sy < img.height and not ink[sx, sy]:
                        px[sx, sy] = shadow

    for y in range(img.height):
        for x in range(img.width):
            if ink[x, y]:
                px[x, y] = fg

    if not compact:
        dr = ImageDraw.Draw(img)
        for i, (cp, g) in enumerate(items):
            r, c = divmod(i, cols)
            x0 = c * cw
            y0 = r * ch
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], outline=(210, 210, 210))
            label = f"{cp:04X}"
            if 0x20 <= cp < 0x7F:
                label = f"{chr(cp)} {label}"
            dr.text((x0 + 2, y0 + cw + 1), label, fill=(120, 120, 120))
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bdf", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--text", default=None,
                    help="只渲染这些字符（按给定顺序）")
    ap.add_argument("--cols", type=int, default=32)
    ap.add_argument("--rows", type=int, default=24)
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--page", type=int, default=None, help="只出指定页（0 起）")
    ap.add_argument("--compact", action="store_true",
                    help="整版字形图：无网格无标注（同 FONT_ALL.png 风格）")
    ap.add_argument("--fg", default="000000", help="字色 RRGGBB")
    ap.add_argument("--bg", default="FFFFFF", help="底色 RRGGBB")
    ap.add_argument("--shadow", default="none", help="阴影色 RRGGBB；none 关闭")
    ap.add_argument("--single", action="store_true",
                    help="不分页，全部字形挤进一张图（配合 --compact --scale 1）")
    a = ap.parse_args()

    if not a.bdf.is_file():
        raise SystemExit(f"missing {a.bdf}")
    glyphs, meta = parse_bdf(a.bdf)
    print(f"{a.bdf.name}: {len(glyphs)} glyphs  {meta.get('bbox','')}")
    if meta.get("comment"):
        print(f"  {meta['comment']}")

    def hexc(v: str) -> tuple[int, int, int]:
        v = v.lstrip("#")
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))

    sh = None if str(a.shadow).lower() in ("none", "-", "") else hexc(a.shadow)
    sty = dict(compact=a.compact, fg=hexc(a.fg), bg=hexc(a.bg), shadow=sh)

    if a.text:
        want = []
        miss = []
        for ch in a.text:
            cp = ord(ch)
            if cp in glyphs:
                want.append((cp, glyphs[cp]))
            else:
                miss.append(ch)
        if miss:
            print(f"  missing: {''.join(miss)}")
        if not want:
            raise SystemExit("no glyphs matched")
        a.out.parent.mkdir(parents=True, exist_ok=True)
        build_page(want, cols=min(a.cols, len(want)), scale=a.scale, **sty).save(a.out)
        print(f"wrote {a.out}  ({len(want)} glyphs)")
        return 0

    order = sorted(glyphs.items())
    if a.single:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        build_page(order, cols=a.cols, scale=a.scale, **sty).save(a.out)
        print(f"wrote {a.out}  ({len(order)} glyphs, {a.cols} cols)")
        return 0
    per = max(1, a.cols * a.rows)
    pages = [order[i:i + per] for i in range(0, len(order), per)]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sel = range(len(pages)) if a.page is None else [a.page]
    for pi in sel:
        if pi >= len(pages):
            continue
        page = build_page(pages[pi], cols=a.cols, scale=a.scale, **sty)
        if a.page is None and len(pages) > 1:
            out = a.out.with_name(f"{a.out.stem}-p{pi}{a.out.suffix}")
        else:
            out = a.out
        page.save(out)
        print(f"wrote {out}  page {pi + 1}/{len(pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
