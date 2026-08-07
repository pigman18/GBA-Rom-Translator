"""Build Chinese 宝可梦 title logo matching JP Ruby style."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WORK = Path(__file__).resolve().parent
ORIG = WORK / "0x0836D268_compose.png"
DRAFT = Path(
    r"C:\Users\Administrator\.cursor\projects\c-code-GBA-Rom-Translator"
    r"\assets\0x0836D268_compose_zh_draft.png"
)


def build_palette(img: Image.Image) -> list[tuple[int, int, int]]:
    seen: set[tuple[int, int, int]] = set()
    palette: list[tuple[int, int, int]] = []
    for r, g, b, a in img.getdata():
        if a < 10:
            continue
        c = (r, g, b)
        if c not in seen:
            seen.add(c)
            palette.append(c)
    return palette


def nearest(rgb: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    r, g, b = rgb
    best = palette[0]
    bd = 10**18
    for pr, pg, pb in palette:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd = d
            best = (pr, pg, pb)
    return best


def remap(img: Image.Image, palette: list[tuple[int, int, int]]) -> Image.Image:
    out = img.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                px[x, y] = (0, 0, 0, 0)
                continue
            nr, ng, nb = nearest((r, g, b), palette)
            px[x, y] = (nr, ng, nb, 255)
    return out


def is_red(r: int, g: int, b: int) -> bool:
    return r >= 160 and g <= 210 and b <= 210 and r > g + 15 and r > b + 15


def extract_texture(orig: Image.Image) -> Image.Image:
    px = orig.load()
    w, h = orig.size
    tx0, ty0, tx1, ty1 = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 200 or not is_red(r, g, b):
                continue
            tx0 = min(tx0, x)
            ty0 = min(ty0, y)
            tx1 = max(tx1, x)
            ty1 = max(ty1, y)
    tex = Image.new("RGB", (tx1 - tx0 + 1, ty1 - ty0 + 1), (200, 40, 40))
    tpx = tex.load()
    for y in range(ty0, ty1 + 1):
        for x in range(tx0, tx1 + 1):
            r, g, b, a = px[x, y]
            if a >= 200 and is_red(r, g, b):
                tpx[x - tx0, y - ty0] = (r, g, b)
    return tex


def dilate(m: Image.Image, radius: int) -> Image.Image:
    return m.filter(ImageFilter.MaxFilter(radius * 2 + 1))


def render_mask(text: str = "宝可梦", width: int = 180, height: int = 48) -> Image.Image:
    scale = 4
    cw, ch = width * scale, height * scale
    mask_hi = Image.new("L", (cw, ch), 0)
    draw = ImageDraw.Draw(mask_hi)
    font = ImageFont.truetype(r"C:\Windows\Fonts\STHUPO.TTF", 40 * scale)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    ox = (cw - tw) // 2 - bbox[0]
    oy = (ch - th) // 2 - bbox[1] - scale
    # thicken strokes
    rad = int(1.6 * scale)
    for dx in range(-rad, rad + 1):
        for dy in range(-rad, rad + 1):
            if dx * dx + dy * dy <= rad * rad:
                draw.text((ox + dx, oy + dy), text, font=font, fill=255)
    draw.text((ox, oy), text, font=font, fill=255)
    mask = mask_hi.resize((width, height), Image.Resampling.BILINEAR)
    return mask.point(lambda v: 255 if v > 120 else 0)


def pick_color(samples: list[tuple[int, int, int]], fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not samples:
        return fallback
    return samples[len(samples) // 2]


def build_from_mask(orig: Image.Image, palette: list[tuple[int, int, int]]) -> Image.Image:
    w, h = orig.size
    px = orig.load()
    tex = extract_texture(orig)
    tex.save(WORK / "_tex.png")
    tpx = tex.load()
    txx, txy = tex.size

    white_cols: list[tuple[int, int, int]] = []
    dark_cols: list[tuple[int, int, int]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 200:
                continue
            if r > 220 and g > 220 and b > 220:
                white_cols.append((r, g, b))
            elif r < 60 and g < 80 and b < 100 and (r + g + b) > 15:
                dark_cols.append((r, g, b))
    white_fill = pick_color(white_cols, (248, 248, 248))
    dark_fill = pick_color(dark_cols, (32, 40, 48))
    print("white", white_fill, "dark", dark_fill)

    mw, mh = 176, 46
    core = render_mask(width=mw, height=mh)
    core.save(WORK / "_chs_mask.png")
    white_ring = dilate(core, 2)
    dark_ring = dilate(core, 3)

    body_h = mh + 8
    logo = Image.new("RGBA", (mw + 8, body_h), (0, 0, 0, 0))
    lpx = logo.load()
    mpx = core.load()
    wring = white_ring.load()
    dring = dark_ring.load()
    y_off = 2
    x_off = 4
    for y in range(mh):
        for x in range(mw):
            if dring[x, y] == 0:
                continue
            xx, yy = x + x_off, y + y_off
            if mpx[x, y] > 0:
                tr, tg, tb = tpx[(x * txx // mw) % txx, min(y * txy // max(mh - 6, 1), txy - 1)]
                if y < 16:
                    tr = min(248, tr + 18)
                    tg = min(248, tg + 8)
                    tb = min(248, tb + 8)
                lpx[xx, yy] = (tr, tg, tb, 255)
            elif wring[x, y] > 0:
                lpx[xx, yy] = (*white_fill, 255)
            else:
                lpx[xx, yy] = (*dark_fill, 255)

    # tiny ® using white/dark from palette
    draw = ImageDraw.Draw(logo)
    rx, ry = logo.size[0] - 14, 2
    draw.ellipse((rx, ry, rx + 9, ry + 9), outline=white_fill, width=1)
    try:
        f = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 7)
    except OSError:
        f = ImageFont.load_default()
    draw.text((rx + 2, ry), "R", font=f, fill=white_fill)

    logo = remap(logo, palette)
    logo.save(WORK / "_chs_logo_body.png")

    # Extract English + silver banner (non-red in lower band)
    eng = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    epx = eng.load()
    for y in range(40, 66):
        for x in range(18, 165):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if is_red(r, g, b) and r > 190:
                continue
            # keep mid/light greys, whites, blue outlines
            if (abs(r - g) < 40 and abs(g - b) < 40) or (b >= r and b >= g and r < 180):
                epx[x, y] = (r, g, b, a)
            elif r < 50 and g < 60 and b < 70:
                epx[x, y] = (r, g, b, a)
    eng = remap(eng, palette)
    eng.crop((0, 0, 200, 80)).save(WORK / "_eng.png")

    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Place Chinese centered over original logo width (~180)
    bb = logo.getbbox()
    assert bb
    chs_w = bb[2] - bb[0]
    place_x = 10 + max(0, (175 - chs_w) // 2)
    place_y = 8
    result.alpha_composite(logo, (place_x, place_y))
    # English under it (keep original x position so "Pokémon" aligns naturally)
    result.alpha_composite(eng, (0, 0))
    # Chinese on top again so red letters cover leftover JP scraps in banner zone
    result.alpha_composite(logo, (place_x, place_y))
    result = remap(result, palette)
    result.save(WORK / "_compose_zh_v1.png")
    print("v1 bbox", result.getbbox())
    return result


def build_from_draft(orig: Image.Image, palette: list[tuple[int, int, int]]) -> Image.Image:
    draft = Image.open(DRAFT).convert("RGBA")
    dp = draft.load()
    dw, dh = draft.size
    for y in range(dh):
        for x in range(dw):
            r, g, b, a = dp[x, y]
            if r < 18 and g < 18 and b < 18:
                dp[x, y] = (0, 0, 0, 0)
    bb = draft.getbbox()
    assert bb
    cropped = draft.crop(bb)
    target_w = 184
    target_h = max(1, int(cropped.height * target_w / cropped.width))
    cropped = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
    cropped = remap(cropped, palette)
    out = Image.new("RGBA", orig.size, (0, 0, 0, 0))
    out.paste(cropped, (8, 6), cropped)
    out.save(WORK / "_compose_zh_draft_mapped.png")
    print("draft mapped bbox", out.getbbox())
    return out


def main() -> None:
    orig = Image.open(ORIG).convert("RGBA")
    # Prefer backup if compose already overwritten? Use 副本 as JP source if present.
    backup = WORK / "0x0836D268_compose - 副本.png"
    if backup.exists():
        orig = Image.open(backup).convert("RGBA")
        print("using backup JP source")
    palette = build_palette(orig)
    print("palette", len(palette))
    v1 = build_from_mask(orig, palette)
    v2 = build_from_draft(orig, palette)
    # Also save side-by-side preview
    prev = Image.new("RGBA", (520, 280), (0, 0, 0, 255))
    prev.paste(orig.crop((0, 0, 200, 80)), (10, 10))
    prev.paste(v1.crop((0, 0, 200, 80)), (10, 100))
    prev.paste(v2.crop((0, 0, 200, 80)), (10, 190))
    prev.save(WORK / "_preview_compare.png")
    print("wrote preview")


if __name__ == "__main__":
    main()
