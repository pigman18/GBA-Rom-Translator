"""Minimal transplant: 宝可梦.png → compose. Cutout + scale + palette only."""
from __future__ import annotations

import shutil
from collections import deque
from datetime import datetime
from pathlib import Path

from PIL import Image

WORK = Path(__file__).resolve().parent
OUT = WORK / "0x0836D268_compose.png"
JP = WORK / "0x0836D268_compose_jp_bak.png"
SRC = WORK / "宝可梦.png"
BAK = WORK / "bak"

# Full JP logo footprint (glyphs + English banner)
JP_LOGO_BOX = (10, 8, 191, 64)


def backup(path: Path) -> None:
    BAK.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    dest = BAK / f"{path.stem}.{ts}{path.suffix}"
    shutil.copy2(path, dest)
    print("bak", dest.name)


def build_palette(img: Image.Image) -> list[tuple[int, int, int]]:
    seen: set[tuple[int, int, int]] = set()
    pal: list[tuple[int, int, int]] = []
    for r, g, b, a in img.getdata():
        if a < 10:
            continue
        c = (r, g, b)
        if c not in seen:
            seen.add(c)
            pal.append(c)
    return pal


def nearest(rgb: tuple[int, int, int], pal: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    r, g, b = rgb
    best, bd = pal[0], 10**18
    for pr, pg, pb in pal:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd, best = d, (pr, pg, pb)
    return best


def flood_cut_white(img: Image.Image, thr: int = 240) -> Image.Image:
    """Remove edge-connected white background only; keep internal whites."""
    img = img.convert("RGBA")
    w, h = img.size
    p = img.load()
    marked = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    def is_bg(x: int, y: int) -> bool:
        r, g, b, a = p[x, y]
        return a < 10 or (r >= thr and g >= thr and b >= thr)

    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    for x in range(0, w, max(1, w // 16)):
        seeds += [(x, 0), (x, h - 1)]
    for y in range(0, h, max(1, h // 16)):
        seeds += [(0, y), (w - 1, y)]

    for x, y in seeds:
        if is_bg(x, y) and not marked[y * w + x]:
            marked[y * w + x] = 1
            q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not marked[ny * w + nx] and is_bg(nx, ny):
                marked[ny * w + nx] = 1
                q.append((nx, ny))

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    op = out.load()
    # Logo lives in the upper band; ignore watermark at bottom of 2048 canvas
    y_lim = min(h, 560)
    for y in range(y_lim):
        for x in range(w):
            if marked[y * w + x]:
                continue
            r, g, b, a = p[x, y]
            op[x, y] = (r, g, b, 255)
    top = out.crop((0, 0, w, y_lim))
    bb = top.getbbox()
    assert bb, "empty cutout"
    print("cutout bbox", bb)
    return top.crop(bb)


def quantize(img: Image.Image, pal: list[tuple[int, int, int]]) -> Image.Image:
    p = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = p[x, y]
            if a < 10:
                p[x, y] = (0, 0, 0, 0)
            else:
                p[x, y] = (*nearest((r, g, b), pal), 255)
    return img


# JP outer-edge darks (hard silhouette, not soft AI halo)
_JP_DARK = [(16, 16, 16), (24, 32, 40), (32, 40, 48), (40, 56, 64), (56, 48, 56)]


def _nearest_dark(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = rgb
    best, bd = _JP_DARK[0], 10**18
    for pr, pg, pb in _JP_DARK:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd, best = d, (pr, pg, pb)
    return best


def clean_outer_residue(img: Image.Image) -> tuple[int, int]:
    """Remove light halo / mute mid fringe on outer edge only (touching empty)."""
    p = img.load()
    w, h = img.size
    removed = darkened = 0

    def is_empty(x: int, y: int) -> bool:
        if not (0 <= x < w and 0 <= y < h):
            return True
        r, g, b, a = p[x, y]
        return a < 10 or r + g + b < 15

    neigh = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if not (dx == 0 and dy == 0))

    # multi-pass: delete pale halo, darken soft fringe (8-neighbor outer edge)
    for _ in range(3):
        kill: list[tuple[int, int]] = []
        dim: list[tuple[int, int]] = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = p[x, y]
                if a < 10:
                    continue
                if not any(is_empty(x + dx, y + dy) for dx, dy in neigh):
                    continue
                # keep red fill
                if r > 140 and r > g + 30 and r > b + 30:
                    continue
                # keep only very bright white outline tips
                if r + g + b > 720 and min(r, g, b) > 220:
                    continue
                avg = (r + g + b) / 3
                # pale grey / pink halo from white-bg cutout → drop
                if avg >= 85:
                    kill.append((x, y))
                # soft mid fringe → JP dark edge
                elif avg >= 48:
                    dim.append((x, y))
        for x, y in kill:
            p[x, y] = (0, 0, 0, 0)
            removed += 1
        for x, y in dim:
            r, g, b, _ = p[x, y]
            p[x, y] = (*_nearest_dark((r, g, b)), 255)
            darkened += 1

    # unify remaining outer-edge non-fill / non-white to solid JP dark
    for y in range(h):
        for x in range(w):
            r, g, b, a = p[x, y]
            if a < 10:
                continue
            if not any(is_empty(x + dx, y + dy) for dx, dy in neigh):
                continue
            if r > 140 and r > g + 30 and r > b + 30:
                continue
            if r + g + b > 720 and min(r, g, b) > 220:
                continue
            # any leftover mid/brown edge → pure dark
            if (r, g, b) not in _JP_DARK:
                p[x, y] = (16, 16, 16, 255)
                darkened += 1
    return removed, darkened


def main() -> None:
    assert JP.is_file() and SRC.is_file()
    if OUT.is_file():
        backup(OUT)

    jp = Image.open(JP).convert("RGBA")
    pal = build_palette(jp)
    print("palette", len(pal))

    # 1) cutout full logo from source (Chinese + ball + English as designed)
    logo = flood_cut_white(Image.open(SRC), thr=230)
    # hi-res edge clean before downscale (kills soft halo early)
    rm0, dk0 = clean_outer_residue(logo)
    print("logo", logo.size, "hi-res edge", rm0, dk0)

    # 2) scale to fit JP logo box — preserve aspect, no content rewrite
    x0, y0, x1, y1 = JP_LOGO_BOX
    tw, th = x1 - x0, y1 - y0
    iw, ih = logo.size
    scale = min(tw / iw, th / ih)
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    scaled = logo.resize((nw, nh), Image.Resampling.LANCZOS)
    print("scaled", scaled.size, "box", JP_LOGO_BOX)

    # 3) palette only
    scaled = quantize(scaled, pal)
    # 4) clear outer light residue (AI white-bg halo) — edge only
    rm, dk = clean_outer_residue(scaled)
    print("edge clean scaled", "removed", rm, "darkened", dk)

    out = Image.new("RGBA", jp.size, (0, 0, 0, 0))
    px = x0 + (tw - nw) // 2
    py = y0 + (th - nh) // 2
    print("place", px, py)
    out.alpha_composite(scaled, (px, py))
    rm2, dk2 = clean_outer_residue(out)
    print("edge clean final", "removed", rm2, "darkened", dk2)

    pal_set = set(pal)
    off = sum(1 for r, g, b, a in out.getdata() if a >= 10 and (r, g, b) not in pal_set)
    print("off-palette", off, "bbox", out.getbbox())
    out.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
