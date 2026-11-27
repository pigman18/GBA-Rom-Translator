"""把全部 species 的 bot 采集原图（整帧 240x160）拼成一张总览大图。

【用户要求（2026-11-27）】合并大图要用 bot 的原图，**不要裁剪**。
  每格直接放完整一帧，不做任何 CROP，保证看到的就是采集时的画面。

布局：
  每只一格 = 完整 240x160 帧 + 底部编号标签
  横向 N 列，纵向按需。

血条在帧内位置（实测）：
  敌方名字区 x12..139，我方 x126..253
  整帧放上去即可完整看到敌我两侧血条。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path.cwd()
SWEEP = ROOT / "work/POKEMON_RUBY_AXVJ00/sweep"

# bot 原帧尺寸（schema 3 导出的 PNG 为 240x160）
FRAME_W, FRAME_H = 240, 160


def load_font(size: int):
    for name in ("msyh.ttc", "simsun.ttc", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="work/_pokedex_sheet.png")
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--end", type=int, default=386)
    ap.add_argument("--scale", type=int, default=1,
                    help="放大倍数，默认 1（不放大，原帧尺寸）")
    ap.add_argument("--no-label", action="store_true", help="不画编号标签")
    args = ap.parse_args()

    rec_path = SWEEP / "index.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {}

    cells = []
    for sid in range(1, args.end + 1):
        key = str(sid)
        if key not in rec:
            continue
        img = Path(rec[key].get("dir", "")) / "translated.png"
        if not img.exists():
            continue
        cells.append((sid, rec[key].get("zh", "?"), img))

    if not cells:
        print("没有可拼的图")
        return 1

    S = args.scale
    cw = FRAME_W * S
    ch = FRAME_H * S
    label_h = 16 * S if not args.no_label else 0
    PAD = 2
    cell_w = cw + PAD * 2
    cell_h = ch + label_h + PAD * 2

    cols = args.cols
    rows = (len(cells) + cols - 1) // cols
    W = cols * cell_w
    H = rows * cell_h
    print(f"拼图 {len(cells)} 只 -> {cols} 列 x {rows} 行 = {W}x{H}px "
          f"(scale={S}, 每格完整原帧 {FRAME_W}x{FRAME_H})")

    sheet = Image.new("RGB", (W, H), (245, 245, 240))
    dr = ImageDraw.Draw(sheet)
    font = load_font(11 * S) if label_h else None

    for i, (sid, zh, img) in enumerate(cells):
        r, c = divmod(i, cols)
        x = c * cell_w + PAD
        y = r * cell_h + PAD
        # 完整原帧，不裁剪，只做等比放大（scale=1 时即原图）
        im = Image.open(img).convert("RGB")
        if S != 1:
            im = im.resize((cw, ch), Image.NEAREST)
        sheet.paste(im, (x, y))
        if font:
            dr.text((x + 1, y + ch + 1), f"{sid} {zh}", fill=(20, 20, 20), font=font)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"-> {out}  ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
