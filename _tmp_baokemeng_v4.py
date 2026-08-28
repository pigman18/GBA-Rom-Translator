"""v4: aggressive thickening, NO inner dark ring, gradient goes all the way to the bevel.
Also creates a side-by-side comparison image.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import os

ROOT = r"C:\code\GBA-Rom-Translator"
COMPOSE_PNG = os.path.join(ROOT, r"configs\POKEMON_RUBY_AXVJ00\tiles\0x0836D268_compose.png")
PREVIEW_PNG = os.path.join(ROOT, r"configs\POKEMON_RUBY_AXVJ00\tiles\0x0836D268_baokemeng_preview.png")
COMPARE_PNG = os.path.join(ROOT, r"configs\POKEMON_RUBY_AXVJ00\tiles\_compare_baokemeng.png")

# Title bbox
TITLE_X0, TITLE_Y0 = 6, 8
TITLE_X1, TITLE_Y1 = 195, 65
W = TITLE_X1 - TITLE_X0
H = TITLE_Y1 - TITLE_Y0

# Pokemon red palette
COL_DARK     = (148, 8, 8)
COL_RED_MID  = (188, 12, 12)
COL_RED      = (224, 16, 16)
COL_RED_HI   = (240, 24, 24)
COL_PINK     = (248, 100, 100)
COL_WHITE    = (252, 252, 252)

FONT = r"C:\Windows\Fonts\simhei.ttf"


def make_thick_mask(text, font_size, canvas_size, margin=2, stroke=4):
    """Heavy multi-pass to make really chunky strokes."""
    cw, ch = canvas_size
    img = Image.new("L", (cw, ch), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, font_size)
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            d.text((margin + dx, margin + dy), text, fill=255, font=f)
    return img


def render_title(text, w, h):
    SC = 4
    cw, ch = w * SC, h * SC
    target_w = int(w * 0.95) * SC
    target_h = int(h * 0.90) * SC
    margin = 2 * SC
    fs = target_h
    while fs > 8:
        f = ImageFont.truetype(FONT, fs)
        probe = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(probe).text((margin, margin), text, fill=255, font=f)
        bbox = probe.getbbox()
        if bbox is None:
            fs -= 1; continue
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if bw <= target_w and bh <= target_h:
            break
        fs -= 1
    print(f"  Font: {fs}")

    # Build thick mask with heavy multi-pass (5x5 = 9 passes at stroke=4)
    text_mask = make_thick_mask(text, fs, (cw, ch), margin=margin, stroke=4)
    mask = np.array(text_mask) > 0

    # === Layer 1: Drop shadow ===
    shadow_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    shifted = np.roll(mask.astype(np.uint8), shift=(5*SC, 5*SC), axis=(0, 1))
    shifted[:5*SC, :] = 0
    shifted[:, :5*SC] = 0
    shadow_img = Image.fromarray((shifted * 255).astype(np.uint8), "L")
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(2.5))
    shadow_arr[..., 3] = np.array(shadow_img)
    shadow_arr[..., :3] = 0
    shadow = Image.fromarray(shadow_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # === Layer 2: White bevel ring (1 px thick only) ===
    # Erode by 1 px only
    inner_for_bevel = text_mask.filter(ImageFilter.MinFilter(2 + 1))  # 1 px
    ring = (np.array(text_mask) > 0) & (np.array(inner_for_bevel) == 0)
    bevel_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    bevel_arr[ring] = COL_WHITE + (255,)
    bevel = Image.fromarray(bevel_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # === Layer 3: BODY fill goes ALL THE WAY TO THE BEVEL ===
    # (no inner dark ring - that's what was creating the hollow look)
    # Body mask = inner_for_bevel
    body_mask = np.array(inner_for_bevel) > 0

    # Body gradient: smooth, biased top-left (light from top-left)
    yy, xx = np.indices((ch, cw))
    ty = yy / max(1, ch - 1)
    tx = xx / max(1, cw - 1)
    # Smoother gradient - no harsh zones
    bright = (1 - ty) * 0.55 + (1 - tx) * 0.35 + 0.10
    # Add a slight "highlight" bump in top-left of the whole image
    # (this gives a sense of overall lighting)
    bright = np.clip(bright, 0.0, 1.0)

    # Map to Pokemon palette continuously (interpolate, not zone-based)
    # bright=0.0 -> COL_DARK
    # bright=0.4 -> COL_RED
    # bright=0.7 -> COL_RED_HI
    # bright=1.0 -> COL_PINK
    def mix(c0, c1, t):
        return int(c0[0]*(1-t) + c1[0]*t), int(c0[1]*(1-t) + c1[1]*t), int(c0[2]*(1-t) + c1[2]*t)

    body_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    # For speed, do piecewise linear interpolation in vectorized form
    # Pre-compute color stops
    R = np.zeros((ch, cw), dtype=np.float32)
    G = np.zeros((ch, cw), dtype=np.float32)
    B = np.zeros((ch, cw), dtype=np.float32)
    # Stop 0: bright=0 -> COL_DARK
    # Stop 0.4: bright=0.4 -> COL_RED
    # Stop 0.7: bright=0.7 -> COL_RED_HI
    # Stop 1.0: bright=1.0 -> COL_PINK
    # Linear interpolation between stops
    b0, b1, b2, b3 = 0.0, 0.4, 0.7, 1.0
    c0, c1, c2, c3 = COL_DARK, COL_RED, COL_RED_HI, COL_PINK

    seg0 = bright <= b1
    seg1 = (bright > b1) & (bright <= b2)
    seg2 = bright > b2

    t01 = (bright - b0) / (b1 - b0)
    t12 = (bright - b1) / (b2 - b1)
    t23 = (bright - b2) / (b3 - b2)

    # Segment 0: COL_DARK -> COL_RED
    R = np.where(seg0, c0[0]*(1-t01) + c1[0]*t01, R)
    G = np.where(seg0, c0[1]*(1-t01) + c1[1]*t01, G)
    B = np.where(seg0, c0[2]*(1-t01) + c1[2]*t01, B)
    # Segment 1: COL_RED -> COL_RED_HI
    R = np.where(seg1, c1[0]*(1-t12) + c2[0]*t12, R)
    G = np.where(seg1, c1[1]*(1-t12) + c2[1]*t12, G)
    B = np.where(seg1, c1[2]*(1-t12) + c2[2]*t12, B)
    # Segment 2: COL_RED_HI -> COL_PINK
    R = np.where(seg2, c2[0]*(1-t23) + c3[0]*t23, R)
    G = np.where(seg2, c2[1]*(1-t23) + c3[1]*t23, G)
    B = np.where(seg2, c2[2]*(1-t23) + c3[2]*t23, B)

    body_arr[..., 0] = np.clip(R, 0, 255).astype(np.uint8)
    body_arr[..., 1] = np.clip(G, 0, 255).astype(np.uint8)
    body_arr[..., 2] = np.clip(B, 0, 255).astype(np.uint8)
    body_arr[..., 3] = body_mask.astype(np.uint8) * 255
    body = Image.fromarray(body_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # === Composite ===
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(bevel)
    out.alpha_composite(body)
    return out


def main():
    img = Image.open(COMPOSE_PNG).convert("RGBA")
    arr = np.array(img).copy()
    arr[TITLE_Y0:TITLE_Y1, TITLE_X0:TITLE_X1] = [0, 0, 0, 0]
    base = Image.fromarray(arr, "RGBA")

    rendered = render_title("宝可梦", W, H)
    print(f"  Rendered: {rendered.size}")
    base.paste(rendered, (TITLE_X0, TITLE_Y0), rendered)
    base.save(COMPOSE_PNG)

    preview = base.resize((base.size[0] * 4, base.size[1] * 4), Image.NEAREST)
    preview.save(PREVIEW_PNG)
    print(f"  Saved: {COMPOSE_PNG}")


if __name__ == "__main__":
    main()
