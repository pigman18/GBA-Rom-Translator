"""Clean Poké Ball (JP palette) → confirm on magenta → paste on 宝 top-right."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

WORK = Path(__file__).resolve().parent
JP = WORK / "0x0836D268_compose - 副本.png"
OUT = WORK / "0x0836D268_compose.png"
CHS = WORK / "_chs_noball.png"


def build_palette(img: Image.Image) -> list[tuple[int, int, int]]:
    seen: set[tuple[int, int, int]] = set()
    pal: list[tuple[int, int, int]] = []
    for pix in img.getdata():
        r, g, b, a = pix
        if a < 10:
            continue
        c = (r, g, b)
        if c not in seen:
            seen.add(c)
            pal.append(c)
    return pal


def nearest(rgb: tuple[int, int, int], pal: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    r, g, b = rgb
    best = pal[0]
    bd = 10**18
    for pr, pg, pb in pal:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd = d
            best = (pr, pg, pb)
    return best


def make_ball(pal: list[tuple[int, int, int]]) -> Image.Image:
    """13×13 clean circle, red top / white bottom — corners fully transparent."""
    red = nearest((216, 32, 48), pal)
    red_hi = nearest((248, 128, 128), pal)
    white = nearest((248, 248, 248), pal)
    band = nearest((16, 16, 16), pal)
    out = nearest((56, 48, 56), pal)
    # . empty  O outline  R red  H highlight  K band  B button  W white
    rows = [
        "....OOOOO....",
        "...ORRRRRO...",
        "..ORHHHRRRO..",
        ".ORRRRRRRRRO.",
        ".ORRRRRRRRRO.",
        ".ORRRRRRRRRO.",
        ".OKKKBKKKKO.",
        ".OWWWWWWWWO.",
        ".OWWWWWWWWO.",
        ".OWWWWWWWWO.",
        "..OWWWWWWO...",
        "...OWWWWO....",
        "....OOOOO....",
    ]
    # fix row lengths to 13
    rows = [r.ljust(13, ".")[:13] for r in rows]
    n = 13
    ball = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    bp = ball.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            if ch == "O":
                bp[x, y] = (*out, 255)
            elif ch == "R":
                bp[x, y] = (*red, 255)
            elif ch == "H":
                bp[x, y] = (*red_hi, 255)
            elif ch == "K":
                bp[x, y] = (*band, 255)
            elif ch == "B":
                bp[x, y] = (*white, 255)
            elif ch == "W":
                bp[x, y] = (*white, 255)
    # JP handakuten is slightly clockwise — rotate ~10°
    ball = ball.rotate(-10, resample=Image.Resampling.NEAREST, expand=True)
    # drop any opaque black leftovers from expand
    px = ball.load()
    w, h = ball.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r + g + b < 8:
                px[x, y] = (0, 0, 0, 0)
    bb = ball.getbbox()
    assert bb
    return ball.crop(bb)


def bao_bounds(chs: Image.Image) -> tuple[int, int]:
    bb = chs.getbbox()
    assert bb
    cpx = chs.load()
    top0, top1 = bb[1], bb[1] + 26
    cols: list[int] = []
    for x in range(bb[0], bb[2]):
        c = 0
        for y in range(top0, top1):
            r, g, b, a = cpx[x, y]
            if a >= 10 and r > 150 and r > g + 25 and r > b + 25:
                c += 1
        cols.append(c)
    bao_left = bao_right = None
    for i, c in enumerate(cols):
        if bao_left is None and c >= 3:
            bao_left = bb[0] + i
        if bao_left is not None and bao_right is None and i >= 8 and c <= 2:
            ahead = max(cols[j] for j in range(i + 1, min(i + 18, len(cols))))
            behind = max(cols[j] for j in range(max(0, i - 8), i))
            if behind >= 5 and ahead >= 5:
                bao_right = bb[0] + i - 1
                break
    assert bao_left is not None and bao_right is not None
    assert 20 <= bao_right - bao_left <= 55
    return bao_left, bao_right


def main() -> None:
    jp = Image.open(JP).convert("RGBA")
    pal = build_palette(jp)
    chs = Image.open(CHS).convert("RGBA")
    bb = chs.getbbox()
    assert bb

    ball = make_ball(pal)
    # --- CONFIRM before paste ---
    ball.save(WORK / "_ball_cut.png")
    vis = Image.new("RGBA", (ball.size[0] * 18, ball.size[1] * 18), (255, 0, 255, 255))
    vis.alpha_composite(ball.resize((ball.size[0] * 18, ball.size[1] * 18), Image.Resampling.NEAREST))
    vis.save(WORK / "_ball_cut_verify.png")

    # orientation gate
    px = ball.load()
    bw, bh = ball.size
    rt = wb = opaque = 0
    for y in range(bh):
        for x in range(bw):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            opaque += 1
            if r > 150 and r > g + 30 and y < bh // 2:
                rt += 1
            if r > 200 and g > 200 and b > 200 and y >= bh // 2:
                wb += 1
    print(f"CONFIRM ball size={ball.size} opaque={opaque} redTop={rt} whiteBot={wb}")
    assert rt >= 8 and wb >= 8, "ball failed orientation — refuse paste"
    # no opaque black corners
    corners = [(0, 0), (bw - 1, 0), (0, bh - 1), (bw - 1, bh - 1)]
    for x, y in corners:
        assert px[x, y][3] < 10, f"opaque corner at {x},{y} — refuse paste"
    print("ball gates OK — pasting")

    bao_left, bao_right = bao_bounds(chs)
    print("bao", bao_left, "..", bao_right)
    cpx = chs.load()
    top0 = bb[1]
    # rightmost opaque of 宝 upper band (include white outline)
    tr = []
    for y in range(top0, top0 + 16):
        for x in range(bao_right - 8, min(chs.size[0], bao_right + 6)):
            if cpx[x, y][3] >= 10:
                tr.append((x, y))
    max_x = max(x for x, _y in tr)
    min_y = min(y for x, y in tr if x >= max_x - 4)
    print("TR tip", max_x, min_y)

    # sit on top-right shoulder like JP handakuten (overlap outline)
    place_x = max_x - bw + 2
    place_y = max(0, min_y - 1)
    bao_mid = (bao_left + bao_right) // 2
    # force right third of 宝
    place_x = max(place_x, bao_left + 2 * (bao_right - bao_left) // 3)
    print("place", place_x, place_y)

    out = chs.copy()
    out.alpha_composite(ball, (place_x, place_y))
    out.save(OUT)

    crop = (bao_left - 4, max(0, bb[1] - 6), bao_right + 18, bb[1] + 48)
    out.crop(crop).resize((400, 340), Image.Resampling.NEAREST).save(WORK / "_verify_bao_ball_clean.png")
    out.crop((0, 0, 200, 80)).save(WORK / "_verify_full.png")

    jp_z = jp.crop((30, 12, 52, 36)).resize((280, 300), Image.Resampling.NEAREST)
    our_z = out.crop((bao_left, max(0, min_y - 6), bao_right + 14, min_y + 26)).resize(
        (280, 300), Image.Resampling.NEAREST
    )
    cmp = Image.new("RGBA", (580, 320), (0, 0, 0, 255))
    cmp.paste(jp_z, (10, 10))
    cmp.paste(our_z, (300, 10))
    d = ImageDraw.Draw(cmp)
    d.text((10, 0), "JP", fill=(0, 255, 0))
    d.text((300, 0), "CHS", fill=(0, 255, 0))
    cmp.save(WORK / "_compare_jp_chs.png")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
