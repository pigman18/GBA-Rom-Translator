"""Minimal transplant: 红宝石.png → 0x0836EC6C_compose.png. Cutout + scale + palette only."""
from __future__ import annotations

import shutil
from collections import deque
from datetime import datetime
from pathlib import Path

from PIL import Image

WORK = Path(__file__).resolve().parent
OUT = WORK / "0x0836EC6C_compose.png"
JP_BAK = WORK / "0x0836EC6C_compose_jp_bak.png"
SRC = WORK / "红宝石.png"
BAK = WORK / "bak"

# Footprint on 96×32 (slight right pad so 石 outer rim is not canvas-clipped)
JP_BOX = (6, 7, 91, 29)

# Outer-edge dark from this tile (not main-logo blacks)
_EDGE_DARK = [(40, 56, 64), (104, 88, 96), (112, 104, 112)]


def backup(path: Path) -> Path:
    BAK.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    dest = BAK / f"{path.stem}.{ts}{path.suffix}"
    shutil.copy2(path, dest)
    print("bak", dest.name)
    return dest


def build_palette(img: Image.Image) -> list[tuple[int, int, int]]:
    seen: set[tuple[int, int, int]] = set()
    pal: list[tuple[int, int, int]] = []
    for r, g, b, a in img.getdata():
        if a < 10 or r + g + b < 15:
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


def flood_cut_white(img: Image.Image, thr: int = 242, dilate_px: int = 14) -> Image.Image:
    """Cut white paper; keep light outer stroke by dilating dark/colored ink first."""
    import numpy as np

    img = img.convert("RGBA")
    arr = np.asarray(img).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    a = arr[:, :, 3]
    h, w = a.shape

    # Core logo ink: not near-white paper (includes dark rim + red + white inner)
    near_white = (rgb[:, :, 0] >= thr) & (rgb[:, :, 1] >= thr) & (rgb[:, :, 2] >= thr)
    core = (a >= 10) & (~near_white)

    # Dilate core so thin light outer stroke around 石 stays inside protect band
    protect = core.copy()
    for _ in range(max(0, dilate_px)):
        p2 = protect.copy()
        p2[1:, :] |= protect[:-1, :]
        p2[:-1, :] |= protect[1:, :]
        p2[:, 1:] |= protect[:, :-1]
        p2[:, :-1] |= protect[:, 1:]
        protect = p2

    # Flood edge-connected paper white; never eat protected stroke band
    def is_paper(y: int, x: int) -> bool:
        if protect[y, x]:
            return False
        if a[y, x] < 10:
            return True
        return bool(near_white[y, x])

    marked = np.zeros((h, w), dtype=np.uint8)
    q: deque[tuple[int, int]] = deque()
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    for x in range(0, w, max(1, w // 16)):
        seeds += [(x, 0), (x, h - 1)]
    for y in range(0, h, max(1, h // 16)):
        seeds += [(0, y), (w - 1, y)]
    for x, y in seeds:
        if 0 <= x < w and 0 <= y < h and is_paper(y, x) and not marked[y, x]:
            marked[y, x] = 1
            q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not marked[ny, nx] and is_paper(ny, nx):
                marked[ny, nx] = 1
                q.append((nx, ny))

    # Keep unmarked pixels in upper band (drop bottom watermark)
    y_lim = min(h, int(h * 0.92))
    out = np.zeros_like(arr)
    keep = (marked == 0) & (a >= 10)
    keep[y_lim:, :] = False
    # drop flat mid-grey watermark crumbs outside protect
    flat = (
        (np.max(rgb, axis=2) - np.min(rgb, axis=2) < 12)
        & (rgb.sum(axis=2) > 100)
        & (rgb.sum(axis=2) < 200)
        & (~protect)
    )
    keep &= ~flat
    # drop near-black noise
    keep &= rgb.sum(axis=2) >= 40
    out[keep] = arr[keep]
    out[keep, 3] = 255

    top = Image.fromarray(out[:y_lim], "RGBA")
    bb = top.getbbox()
    assert bb, "empty cutout"
    print("cutout bbox", bb, "dilate", dilate_px, "thr", thr)
    return top.crop(bb)


def pad_transparent(img: Image.Image, pad: int) -> Image.Image:
    """Keep cutout off the bitmap edge so LANCZOS does not clip 石 tip."""
    out = Image.new("RGBA", (img.size[0] + 2 * pad, img.size[1] + 2 * pad), (0, 0, 0, 0))
    out.paste(img, (pad, pad))
    return out


def strip_residual_paper(img: Image.Image, thr: int = 252) -> tuple[Image.Image, int]:
    """Delete exterior pure-paper white; never eat whites that hug dark/red ink."""
    import numpy as np

    arr = np.asarray(img.convert("RGBA")).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    a = arr[:, :, 3]
    h, w = a.shape
    empty = (a < 10) | (rgb.sum(axis=2) < 15)
    paper = (a >= 10) & (rgb[:, :, 0] >= thr) & (rgb[:, :, 1] >= thr) & (rgb[:, :, 2] >= thr)
    ink = (a >= 10) & ~paper
    hug = np.zeros((h, w), dtype=bool)
    hug[:, 1:] |= ink[:, :-1]
    hug[:, :-1] |= ink[:, 1:]
    hug[1:, :] |= ink[:-1, :]
    hug[:-1, :] |= ink[1:, :]
    traversable = empty | (paper & ~hug)

    marked = np.zeros((h, w), dtype=np.uint8)
    q: deque[tuple[int, int]] = deque()
    ys, xs = np.where(empty)
    for x, y in zip(xs.tolist(), ys.tolist()):
        marked[y, x] = 1
        q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < w and 0 <= ny < h) or marked[ny, nx]:
                continue
            if traversable[ny, nx]:
                marked[ny, nx] = 1
                q.append((nx, ny))
    kill = paper & ~hug & (marked == 1)
    n = int(kill.sum())
    arr[kill] = (0, 0, 0, 0)
    return Image.fromarray(arr.copy(), "RGBA"), n



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


def _nearest_dark(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = rgb
    best, bd = _EDGE_DARK[0], 10**18
    for pr, pg, pb in _EDGE_DARK:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd, best = d, (pr, pg, pb)
    return best


def clean_outer_residue(img: Image.Image) -> tuple[Image.Image, int, int]:
    """Trim soft paper halo only; keep designed light outer stroke + dark rim."""
    import numpy as np

    arr = np.asarray(img.convert("RGBA")).copy()
    h, w = arr.shape[:2]
    removed = darkened = 0

    def is_empty(x: int, y: int) -> bool:
        if not (0 <= x < w and 0 <= y < h):
            return True
        r, g, b, a = arr[y, x]
        return a < 10 or int(r) + int(g) + int(b) < 15

    def touches_dark_ink(x: int, y: int) -> bool:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            r, g, b, a = arr[ny, nx]
            if a >= 10 and int(r) + int(g) + int(b) < 160:
                return True
        return False

    neigh = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if not (dx == 0 and dy == 0))

    kill: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = (int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2]), int(arr[y, x, 3]))
            if a < 10:
                continue
            if not any(is_empty(x + dx, y + dy) for dx, dy in neigh):
                continue
            if r > 140 and r > g + 30 and r > b + 30:
                continue
            if touches_dark_ink(x, y):
                continue
            if r + g + b > 600 and min(r, g, b) > 180:
                continue
            avg = (r + g + b) / 3
            if avg >= 200 and max(r, g, b) - min(r, g, b) < 20:
                kill.append((x, y))
    for x, y in kill:
        arr[y, x] = (0, 0, 0, 0)
        removed += 1

    for y in range(h):
        for x in range(w):
            r, g, b, a = (int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2]), int(arr[y, x, 3]))
            if a < 10:
                continue
            if not any(is_empty(x + dx, y + dy) for dx, dy in neigh):
                continue
            if r > 140 and r > g + 30 and r > b + 30:
                continue
            if r + g + b > 450:
                continue
            if 50 <= (r + g + b) / 3 < 120 and (r, g, b) not in _EDGE_DARK:
                d = _nearest_dark((r, g, b))
                arr[y, x] = (d[0], d[1], d[2], 255)
                darkened += 1
    return Image.fromarray(arr.copy(), "RGBA"), removed, darkened



def ensure_right_dark_rim(
    img: Image.Image, dark: tuple[int, int, int] = (40, 56, 64)
) -> tuple[Image.Image, int]:
    """If a row's rightmost ink is not dark, paint 1px dark to its right (石 tip)."""
    import numpy as np

    arr = np.asarray(img.convert("RGBA")).copy()
    h, w = arr.shape[:2]
    added = 0
    for y in range(h):
        xs = np.where((arr[y, :, 3] >= 10) & (arr[y, :, :3].sum(axis=1) >= 15))[0]
        if xs.size == 0:
            continue
        x = int(xs.max())
        r, g, b = (int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2]))
        if r + g + b >= 160 and x + 1 < w and arr[y, x + 1, 3] < 10:
            arr[y, x + 1] = (dark[0], dark[1], dark[2], 255)
            added += 1
    return Image.fromarray(arr.copy(), "RGBA"), added


def drop_small_islands(img: Image.Image, max_size: int = 12) -> int:
    """Delete tiny disconnected crumbs (watermark bits / scale dust)."""
    p = img.load()
    w, h = img.size

    def opaque(x: int, y: int) -> bool:
        r, g, b, a = p[x, y]
        return a >= 10 and r + g + b >= 15

    seen = [[False] * w for _ in range(h)]
    removed = 0
    for y in range(h):
        for x in range(w):
            if seen[y][x] or not opaque(x, y):
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[y][x] = True
            cells: list[tuple[int, int]] = []
            while q:
                cx, cy = q.popleft()
                cells.append((cx, cy))
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and opaque(nx, ny):
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if len(cells) <= max_size:
                for cx, cy in cells:
                    p[cx, cy] = (0, 0, 0, 0)
                    removed += 1
    return removed


def main() -> None:
    assert SRC.is_file(), SRC
    assert OUT.is_file() or JP_BAK.is_file(), "need compose or jp_bak"

    if OUT.is_file():
        backup(OUT)
    # Keep a stable JP baseline for palette / box (first run freezes current compose)
    if not JP_BAK.is_file():
        src_jp = OUT if OUT.is_file() else None
        assert src_jp is not None
        shutil.copy2(src_jp, JP_BAK)
        print("jp_bak created", JP_BAK.name)

    jp = Image.open(JP_BAK).convert("RGBA")
    pal = build_palette(jp)
    print("palette", len(pal), "canvas", jp.size)

    logo = flood_cut_white(Image.open(SRC), thr=242, dilate_px=22)
    logo, n_paper = strip_residual_paper(logo, thr=252)
    print("strip paper", n_paper)
    logo, rm0, dk0 = clean_outer_residue(logo)
    print("logo", logo.size, "hi-res edge", rm0, dk0)
    bb = logo.getbbox()
    if bb:
        logo = logo.crop(bb)

    x0, y0, x1, y1 = JP_BOX
    tw, th = x1 - x0, y1 - y0
    # Transparent pad so 石 right tip is not on the bitmap edge during LANCZOS
    logo = pad_transparent(logo, 16)
    iw, ih = logo.size
    scale = min(tw / iw, th / ih)
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    scaled = logo.resize((nw, nh), Image.Resampling.LANCZOS)
    print("scaled", scaled.size, "box", JP_BOX)

    scaled = quantize(scaled, pal)
    scaled, rm, dk = clean_outer_residue(scaled)
    print("edge clean scaled", "removed", rm, "darkened", dk)

    out = Image.new("RGBA", jp.size, (0, 0, 0, 0))
    px = x0 + (tw - nw) // 2
    py = y0 + (th - nh) // 2
    print("place", px, py)
    out.alpha_composite(scaled, (px, py))
    isl = drop_small_islands(out, max_size=8)
    print("islands", isl)
    out, n_right = ensure_right_dark_rim(out)
    print("right dark rim", n_right)
    out = quantize(Image.fromarray(__import__("numpy").asarray(out).copy(), "RGBA"), pal)

    pal_set = set(pal)
    off = sum(1 for r, g, b, a in out.getdata() if a >= 10 and (r, g, b) not in pal_set)
    print("off-palette", off, "bbox", out.getbbox())
    out.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
