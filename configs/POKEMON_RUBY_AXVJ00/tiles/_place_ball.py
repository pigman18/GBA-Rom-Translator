"""Paste confirmed _ball_cut.png onto 宝 top-right. Requires prior visual OK on _ball_cut_verify.png."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

WORK = Path(__file__).resolve().parent
OUT = WORK / "0x0836D268_compose.png"
BALL = WORK / "_ball_cut.png"
CHS = WORK / "_chs_noball.png"
JP = WORK / "0x0836D268_compose - 副本.png"


def main() -> None:
    ball = Image.open(BALL).convert("RGBA")
    chs = Image.open(CHS).convert("RGBA")
    bb = chs.getbbox()
    assert bb
    cpx = chs.load()
    top0, top1 = bb[1], bb[1] + 26

    # Red body only — white outline connects glyphs and breaks gaps
    cols: list[int] = []
    for x in range(bb[0], bb[2]):
        c = 0
        for y in range(top0, top1):
            r, g, b, a = cpx[x, y]
            if a >= 10 and r > 150 and r > g + 25 and r > b + 25:
                c += 1
        cols.append(c)

    # Find first gap (local min after ink) → end of 宝
    bao_left = None
    bao_right = None
    for i, c in enumerate(cols):
        x = bb[0] + i
        if bao_left is None and c >= 3:
            bao_left = x
        if bao_left is not None and bao_right is None and i >= 8:
            # gap: low density with stronger ink soon after
            if c <= 2:
                ahead = max(cols[j] for j in range(i + 1, min(i + 18, len(cols))))
                behind = max(cols[j] for j in range(max(0, i - 8), i))
                if behind >= 5 and ahead >= 5:
                    bao_right = bb[0] + i - 1
                    break
    assert bao_left is not None and bao_right is not None, "bao bounds failed"
    print("bao", bao_left, "..", bao_right, "w", bao_right - bao_left)
    assert 20 <= bao_right - bao_left <= 55, "bao width absurd — segmentation failed"

    tr: list[tuple[int, int]] = []
    for y in range(top0, top0 + 16):
        for x in range(max(bao_left, bao_right - 14), bao_right + 1):
            if cpx[x, y][3] >= 10:
                tr.append((x, y))
    max_x = max(x for x, _y in tr)
    top_y = min(y for x, y in tr if x >= max_x - 4)
    print("TR tip", max_x, top_y)

    bw, bh = ball.size
    # On shoulder of 宝 (overlap glyph), like JP handakuten on ポ
    ball_cx = max_x - 2
    ball_cy = top_y + 5
    place_x = ball_cx - bw // 2
    place_y = ball_cy - bh // 2
    bao_mid = (bao_left + bao_right) // 2
    place_x = max(place_x, bao_mid)
    print("place", place_x, place_y, "cx", place_x + bw // 2, "mid", bao_mid)
    assert place_x + bw // 2 > bao_mid

    out = chs.copy()
    out.alpha_composite(ball, (place_x, place_y))
    out.save(OUT)

    crop = (bao_left - 4, max(0, bb[1] - 6), bao_right + 22, bb[1] + 52)
    clean = out.crop(crop).resize((380, 320), Image.Resampling.NEAREST)
    clean.save(WORK / "_verify_bao_ball_clean.png")
    marked = clean.copy()
    d = ImageDraw.Draw(marked)
    sx = (place_x - crop[0]) * (380 / (crop[2] - crop[0]))
    sy = (place_y - crop[1]) * (320 / (crop[3] - crop[1]))
    scale_x = 380 / (crop[2] - crop[0])
    scale_y = 320 / (crop[3] - crop[1])
    d.rectangle((sx, sy, sx + bw * scale_x, sy + bh * scale_y), outline=(0, 255, 0))
    d.line(
        ((bao_mid - crop[0]) * scale_x, 0, (bao_mid - crop[0]) * scale_x, 320),
        fill=(255, 255, 0),
    )
    marked.save(WORK / "_verify_bao_ball.png")
    out.crop((0, 0, 200, 80)).save(WORK / "_verify_full.png")

    jp = Image.open(JP).convert("RGBA")
    jp_z = jp.crop((28, 10, 55, 40)).resize((270, 300), Image.Resampling.NEAREST)
    our_z = out.crop((bao_left - 2, max(0, top_y - 8), bao_right + 16, top_y + 28)).resize(
        (270, 300), Image.Resampling.NEAREST
    )
    cmp = Image.new("RGBA", (560, 320), (0, 0, 0, 255))
    cmp.paste(jp_z, (0, 10))
    cmp.paste(our_z, (290, 10))
    d = ImageDraw.Draw(cmp)
    d.text((10, 0), "JP", fill=(0, 255, 0))
    d.text((300, 0), "CHS", fill=(0, 255, 0))
    cmp.save(WORK / "_compare_jp_chs.png")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
