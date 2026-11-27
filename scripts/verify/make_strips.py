"""把 386 只血条按 20 只一条拼成长条图，便于逐条逐字读图审核。

每条输出 work/_strips/strip_NN.png，一行 20 格，每格裁敌方名字行并放大 5 倍。
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path.cwd()
SWEEP = ROOT / "work/POKEMON_RUBY_AXVJ00/sweep"
OUT = ROOT / "work/_strips"
CROP = (10, 14, 122, 32)     # 敌方名字行（含框上沿与 Lv）
SCALE = 5
PER = 20


def font(size: int):
    for n in ("msyh.ttc", "simsun.ttc"):
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    idx = json.loads((SWEEP / "index.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    items = []
    for sid in range(1, 387):
        k = str(sid)
        if k not in idx:
            continue
        p = Path(idx[k]["dir"]) / "translated.png"
        if p.exists():
            items.append((sid, idx[k]["zh"], p))

    cw = (CROP[2] - CROP[0]) * SCALE
    ch = (CROP[3] - CROP[1]) * SCALE
    lab = 16
    f = font(12)

    n = 0
    for b in range(0, len(items), PER):
        batch = items[b:b + PER]
        cols = 4
        rows = (len(batch) + cols - 1) // cols
        W = cols * (cw + 6)
        H = rows * (ch + lab + 6)
        im = Image.new("RGB", (W, H), (245, 245, 240))
        dr = ImageDraw.Draw(im)
        for i, (sid, zh, p) in enumerate(batch):
            r, c = divmod(i, cols)
            x = c * (cw + 6) + 3
            y = r * (ch + lab + 6) + 3
            cell = Image.open(p).convert("RGB").crop(CROP)
            cell = cell.resize((cw, ch), Image.NEAREST)
            im.paste(cell, (x, y))
            dr.text((x + 1, y + ch + 1), f"{sid} {zh}", fill=(0, 0, 0), font=f)
        n += 1
        im.save(OUT / f"strip_{n:02d}.png")
    print(f"生成 {n} 条 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
