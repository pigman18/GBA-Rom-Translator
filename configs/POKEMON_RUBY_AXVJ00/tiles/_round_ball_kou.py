"""Always rebuild from 副本(2): fringe + keep extract_ball + place. No stacked edits."""
from __future__ import annotations

import math
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image

WORK = Path(__file__).resolve().parent
OUT = WORK / "0x0836D268_compose.png"
SRC2 = next(p for p in WORK.glob("0x0836D268_compose*") if "(2)" in p.name)
JP = WORK / "0x0836D268_compose - 副本.png"
BAK = WORK / "bak"
DARK = [(16, 16, 16), (24, 32, 40), (32, 40, 48), (40, 56, 64), (56, 48, 56)]
OUTLINE = (24, 32, 40)

# 口 center on 可 (fresh from 副本2 each run; only fringe + extract_ball + place)
KOU_CX, KOU_CY = 85.0, 32.0
JCX, JCY, JRAD = 41.0, 22.0, 6.2


def backup(path: Path) -> None:
    BAK.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    dest = BAK / f"{path.stem}.{ts}{path.suffix}"
    shutil.copy2(path, dest)
    print("bak", dest.name)


def nearest(rgb, pal):
    r, g, b = rgb
    best, bd = pal[0], 10**18
    for pr, pg, pb in pal:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd, best = d, (pr, pg, pb)
    return best


def nearest_d(rgb):
    r, g, b = rgb
    best, bd = DARK[0], 10**18
    for pr, pg, pb in DARK:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd, best = d, (pr, pg, pb)
    return best


def build_palette(img):
    seen, pal = set(), []
    for px in img.getdata():
        r, g, b, a = px
        if a < 10:
            continue
        c = (r, g, b)
        if c not in seen:
            seen.add(c)
            pal.append(c)
    return pal


def fix_fringe(img: Image.Image) -> int:
    p = img.load()
    w, h = img.size
    n = 0

    def is_empty(x, y):
        if not (0 <= x < w and 0 <= y < h):
            return True
        r, g, b, a = p[x, y]
        return a < 10 or r + g + b < 25

    for y in range(h):
        for x in range(w):
            r, g, b, a = p[x, y]
            if a < 10 or (r + g + b) / 3 <= 70:
                continue
            if r > 140 and r > g + 30 and r > b + 30:
                continue
            if not any(is_empty(x + dx, y + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                continue
            if (r + g + b) / 3 >= 100:
                p[x, y] = (*nearest_d((r, g, b)), 255)
                n += 1
    return n


def extract_ball(jp: Image.Image, pal):
    """Kept: JP circular cutout + 1px dark ring (user-approved)."""
    pad = 8
    x0, y0 = int(JCX - JRAD - pad), int(JCY - JRAD - pad)
    raw = jp.crop((x0, y0, int(JCX + JRAD + pad + 1), int(JCY + JRAD + pad + 1)))
    rp = raw.load()
    rw, rh = raw.size
    lcx, lcy = JCX - x0, JCY - y0
    ball = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    bp = ball.load()
    for y in range(rh):
        for x in range(rw):
            d = math.hypot(x - lcx, y - lcy)
            if d > JRAD + 0.2:
                continue
            r, g, b, a = rp[x, y]
            if a < 10:
                continue
            gx, gy = x0 + x, y0 + y
            if r > 145 and r > g + 22 and gx <= JCX - 3.2 and d > JRAD * 0.65 and gx > 0:
                rr, gg, bb, aa = jp.getpixel((gx - 1, gy))
                if (
                    aa >= 10
                    and rr > 145
                    and rr > gg + 22
                    and (gx - 1 - JCX) ** 2 + (gy - JCY) ** 2 > (JRAD * 1.0) ** 2
                ):
                    continue
            if r + g + b < 10 and d > JRAD - 1.0:
                continue
            bp[x, y] = (*nearest((r, g, b), pal), 255)
    bb = ball.getbbox()
    assert bb
    ball = ball.crop(bb)
    bw, bh = ball.size
    side = max(bw, bh)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(ball, ((side - bw) // 2, (side - bh) // 2))
    cp = canvas.load()
    cc = (side - 1) / 2.0
    crad = side / 2.0 - 0.35
    for y in range(side):
        for x in range(side):
            if math.hypot(x - cc, y - cc) > crad:
                cp[x, y] = (0, 0, 0, 0)
    out_ball = Image.new("RGBA", (side + 2, side + 2), (0, 0, 0, 0))
    out_ball.alpha_composite(canvas, (1, 1))
    op = out_ball.load()
    oc = nearest(OUTLINE, pal)
    for y in range(side + 2):
        for x in range(side + 2):
            d = math.hypot(x - (cc + 1), y - (cc + 1))
            if crad - 0.05 < d <= crad + 1.0 and op[x, y][3] < 10:
                op[x, y] = (*oc, 255)
    return out_ball


def main() -> None:
    assert SRC2.is_file(), SRC2
    assert JP.is_file(), JP
    if OUT.is_file():
        backup(OUT)

    # ALWAYS fresh from 副本(2) — never stack on previous compose
    print("base", SRC2.name)
    out = Image.open(SRC2).convert("RGBA")
    print("fringe", fix_fringe(out))

    jp = Image.open(JP).convert("RGBA")
    pal = build_palette(jp)
    ball = extract_ball(jp, pal)
    bw, bh = ball.size
    print("ball", bw, bh)

    place_x = int(round(KOU_CX - (bw - 1) / 2))
    place_y = int(round(KOU_CY - (bh - 1) / 2))
    print("口 center", KOU_CX, KOU_CY, "place", place_x, place_y)

    # punch only under opaque ball pixels, then composite
    p = out.load()
    bp = ball.load()
    for by in range(bh):
        for bx in range(bw):
            if bp[bx, by][3] < 10:
                continue
            x, y = place_x + bx, place_y + by
            if 0 <= x < out.size[0] and 0 <= y < out.size[1]:
                p[x, y] = (0, 0, 0, 0)
    out.alpha_composite(ball, (place_x, place_y))
    out.save(OUT)

    # ascii check
    print("---")
    print("x:  " + "".join(f"{x % 10}" for x in range(70, 100)))
    for y in range(22, 44):
        row = f"{y:02d} "
        for x in range(70, 100):
            r, g, b, a = p[x, y]
            if a < 10:
                row += "."
            elif r + g + b > 520:
                row += "W"
            elif r > 170 and r > g + 40:
                row += "R"
            elif r > 130 and r > g + 20:
                row += "r"
            elif r + g + b < 90:
                row += "#"
            elif r + g + b > 350:
                row += "w"
            else:
                row += "g"
        print(row)

    print("saved", OUT.name)


if __name__ == "__main__":
    main()
