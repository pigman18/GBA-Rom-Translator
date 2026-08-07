"""Finalize Chinese title logo: AI body + original EN banner, palette-locked."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

WORK = Path(__file__).resolve().parent
JP_SRC = WORK / "0x0836D268_compose - 副本.png"
if not JP_SRC.exists():
    JP_SRC = WORK / "0x0836D268_compose.png"
OUT = WORK / "0x0836D268_compose.png"
DRAFT = Path(
    r"C:\Users\Administrator\.cursor\projects\c-code-GBA-Rom-Translator"
    r"\assets\0x0836D268_compose_zh_draft.png"
)
BODY_ONLY = Path(
    r"C:\Users\Administrator\.cursor\projects\c-code-GBA-Rom-Translator"
    r"\assets\chs_logo_body_only.png"
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


def remap(img: Image.Image, palette: list[tuple[int, int, int]], alpha_cut: int = 40) -> Image.Image:
    out = img.convert("RGBA").copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < alpha_cut or (r < 10 and g < 10 and b < 10):
                px[x, y] = (0, 0, 0, 0)
                continue
            nr, ng, nb = nearest((r, g, b), palette)
            px[x, y] = (nr, ng, nb, 255)
    return out


def black_to_alpha(img: Image.Image, thr: int = 18) -> Image.Image:
    out = img.convert("RGBA")
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r <= thr and g <= thr and b <= thr:
                px[x, y] = (0, 0, 0, 0)
    return out


def is_strong_red(r: int, g: int, b: int) -> bool:
    return r >= 170 and g <= 200 and b <= 200 and r > g + 25 and r > b + 25


def extract_english_banner(jp: Image.Image) -> Image.Image:
    """Keep original Pokémon English + metallic base; drop red JP fill."""
    w, h = jp.size
    px = jp.load()
    eng = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    epx = eng.load()
    for y in range(38, 66):
        for x in range(10, 195):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if is_strong_red(r, g, b):
                continue
            # Keep greys/whites/blues that form banner + English
            bright = (r + g + b) / 3
            if bright >= 70 or (b >= r - 5 and g >= 40):
                epx[x, y] = (r, g, b, a)
            elif r < 55 and g < 70 and b < 85 and bright > 12:
                epx[x, y] = (r, g, b, a)
    return eng


def prepare_chs_body(src: Path, palette: list[tuple[int, int, int]], target_w: int = 178) -> Image.Image:
    img = black_to_alpha(Image.open(src))
    bb = img.getbbox()
    if not bb:
        raise RuntimeError(f"empty body: {src}")
    cropped = img.crop(bb)
    # Prefer slightly taller Chinese glyphs; clamp height ~42-48px for body (EN sits below)
    tw = target_w
    th = int(cropped.height * tw / cropped.width)
    if th > 52:
        th = 52
        tw = max(1, int(cropped.width * th / cropped.height))
    # Downscale via BOX then nearest for chunkier pixels
    mid = cropped.resize((tw * 2, th * 2), Image.Resampling.BOX)
    mid = mid.resize((tw, th), Image.Resampling.NEAREST)
    # Mild sharpen before remap
    mid = mid.filter(ImageFilter.SHARPEN)
    return remap(mid, palette, alpha_cut=60)


def main() -> None:
    jp = Image.open(JP_SRC).convert("RGBA")
    palette = build_palette(jp)
    print("palette", len(palette), "src", JP_SRC.name)

    eng = extract_english_banner(jp)
    eng = remap(eng, palette, alpha_cut=10)
    eng.crop((0, 0, 200, 80)).save(WORK / "_eng_clean.png")

    candidates: list[tuple[str, Path]] = []
    if BODY_ONLY.exists():
        candidates.append(("body_only", BODY_ONLY))
    if DRAFT.exists():
        candidates.append(("full_draft", DRAFT))
    mapped = WORK / "_compose_zh_draft_mapped.png"
    if mapped.exists():
        candidates.append(("prev_mapped", mapped))

    best_name = None
    best_img = None
    for name, path in candidates:
        try:
            if name == "prev_mapped":
                body = Image.open(path).convert("RGBA")
                # strip english-ish lower part if present: keep mainly upper red logo
                bb = body.getbbox()
                if bb:
                    # crop top portion of existing mapped draft as body
                    top = body.crop((bb[0], bb[1], bb[2], min(bb[3], bb[1] + 50)))
                    top = black_to_alpha(top)
                    tbb = top.getbbox()
                    if tbb:
                        top = top.crop(tbb)
                    body = remap(top, palette, alpha_cut=50)
            else:
                body = prepare_chs_body(path, palette)
            body.save(WORK / f"_body_{name}.png")
            print(name, "body", body.size, body.getbbox())
            if best_img is None or name == "body_only":
                best_name, best_img = name, body
        except Exception as e:
            print("skip", name, e)

    assert best_img is not None
    print("using", best_name)

    w, h = jp.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bb = best_img.getbbox()
    assert bb
    body_w = bb[2] - bb[0]
    # Center Chinese over original logo center (~100)
    place_x = max(6, 12 + (170 - body_w) // 2)
    place_y = 6

    # Banner first, then Chinese on top (Chinese bottom may slightly overlap banner top like JP)
    out.alpha_composite(eng, (0, 0))
    out.alpha_composite(best_img, (place_x, place_y))
    out = remap(out, palette, alpha_cut=10)

    out.save(OUT)
    out.crop((0, 0, 210, 80)).save(WORK / "_final_crop.png")
    print("wrote", OUT, "bbox", out.getbbox())

    # preview vs JP
    prev = Image.new("RGBA", (420, 100), (0, 0, 0, 255))
    prev.paste(jp.crop((0, 0, 200, 80)), (10, 10))
    prev.paste(out.crop((0, 0, 200, 80)), (220, 10))
    prev.save(WORK / "_final_preview.png")


if __name__ == "__main__":
    main()
