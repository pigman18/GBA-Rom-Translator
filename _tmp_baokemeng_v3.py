"""Pokemon-style 宝可梦 title v3 - using exact Pokemon palette + smooth radial-ish gradient.

Key changes from v1/v2:
- v1 was "font + discrete color steps" -> looked like a filter on a font
- v2 was "directional lighting only on edges" -> hollow look
- v3: smooth radial-style gradient (light from top-left, dark to bottom-right)
       with EXACT Pokemon red palette
- Use a multi-pass heavy stroke (4 passes at slight offsets) for chunky bold strokes
- Tighter white bevel
- Larger drop shadow offset for clearer 3D feel

Still using SimHei because it's the cleanest available Chinese font.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import os

ROOT = r"C:\code\GBA-Rom-Translator"
COMPOSE_PNG = os.path.join(ROOT, r"configs\POKEMON_RUBY_AXVJ00\tiles\0x0836D268_compose.png")
PREVIEW_PNG = os.path.join(ROOT, r"configs\POKEMON_RUBY_AXVJ00\tiles\0x0836D268_baokemeng_preview.png")

# Title bbox
TITLE_X0, TITLE_Y0 = 6, 8
TITLE_X1, TITLE_Y1 = 195, 65
W = TITLE_X1 - TITLE_X0
H = TITLE_Y1 - TITLE_Y0

# Pokemon red palette (sampled from 红宝石.png)
COL_BGND     = (0, 0, 0)
COL_DARK     = (132, 8, 8)         # very dark red (inner shadow / shadow side)
COL_RED_MID  = (176, 12, 12)       # dark red
COL_RED      = (224, 16, 16)       # main red (matches red宝石.png)
COL_RED_HI   = (240, 24, 24)       # bright red
COL_PINK     = (248, 96, 96)       # pink highlight (top edge)
COL_WHITE    = (252, 252, 252)     # pure white (bevel + top edge)

FONT = r"C:\Windows\Fonts\simhei.ttf"


def make_thick_mask(text, font_size, canvas_size, margin=2, stroke=3):
    """Render text with multiple offset passes to create thick chunky strokes."""
    cw, ch = canvas_size
    img = Image.new("L", (cw, ch), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, font_size)
    # 5x5 pass for chunky look
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            d.text((margin + dx, margin + dy), text, fill=255, font=f)
    return img


def render_title(text, w, h):
    SC = 4
    cw, ch = w * SC, h * SC

    # Find font size
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

    # Build thick text mask
    text_mask = make_thick_mask(text, fs, (cw, ch), margin=margin, stroke=3)
    # Convert to bool numpy for processing
    mask = np.array(text_mask) > 0

    # === Layer 1: Drop shadow (offset down-right, slightly blurred) ===
    shadow_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    shifted = np.roll(mask.astype(np.uint8), shift=(5*SC, 4*SC), axis=(0, 1))
    shifted[:5*SC, :] = 0
    shifted[:, :4*SC] = 0
    # Dilate shadow slightly for soft edge
    shadow_img = Image.fromarray((shifted * 255).astype(np.uint8), "L")
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(2))
    shadow_arr[..., 3] = np.array(shadow_img)
    shadow_arr[..., :3] = 0
    shadow = Image.fromarray(shadow_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # === Layer 2: White bevel ring (outermost thin ring) ===
    # White ring: pixels that are in mask but not in mask-eroded-by-2px
    inner_for_bevel = text_mask.filter(ImageFilter.MinFilter(2 * 2 + 1))
    ring = (np.array(text_mask) > 0) & (np.array(inner_for_bevel) == 0)
    bevel_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    bevel_arr[ring] = COL_WHITE + (255,)
    bevel = Image.fromarray(bevel_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # === Layer 3: Dark inner ring (just inside the white bevel) ===
    # 1px ring inside the white = dark red
    dark_inner = inner_for_bevel.filter(ImageFilter.MinFilter(1 * 2 + 1))
    dark_ring = (np.array(inner_for_bevel) > 0) & (np.array(dark_inner) == 0)
    dark_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    dark_arr[dark_ring] = COL_DARK + (255,)
    dark_layer = Image.fromarray(dark_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # === Layer 4: Body fill with smooth Pokemon-red gradient ===
    # Compute gradient with bias toward top-left (light source from top-left)
    # For each pixel in mask: combine (1 - y/ch) * 0.55 + (1 - x/cw) * 0.45
    # => 1.0 at top-left, 0.0 at bottom-right
    yy, xx = np.indices((ch, cw))
    # Normalized position 0..1
    ty = yy / max(1, ch - 1)
    tx = xx / max(1, cw - 1)
    # Light source: top-left. Brightness: 1 at top-left, 0 at bottom-right
    # Use a combination: more weight on diagonal to feel "lit"
    bright = (1 - ty) * 0.5 + (1 - tx) * 0.4 + 0.1
    bright = np.clip(bright, 0.0, 1.0)
    # Map brightness to Pokemon palette stops:
    #   bright >= 0.85: COL_PINK
    #   0.65 <= bright < 0.85: COL_RED_HI
    #   0.40 <= bright < 0.65: COL_RED
    #   bright < 0.40: COL_RED_MID
    r = np.where(bright >= 0.85, COL_PINK[0],
                 np.where(bright >= 0.65, COL_RED_HI[0],
                          np.where(bright >= 0.40, COL_RED[0], COL_RED_MID[0])))
    g = np.where(bright >= 0.85, COL_PINK[1],
                 np.where(bright >= 0.65, COL_RED_HI[1],
                          np.where(bright >= 0.40, COL_RED[1], COL_RED_MID[1])))
    b_ch = np.where(bright >= 0.85, COL_PINK[2],
                    np.where(bright >= 0.65, COL_RED_HI[2],
                             np.where(bright >= 0.40, COL_RED[2], COL_RED_MID[2])))
    # Body is in the inner shape (text_mask minus bevel minus dark ring)
    body_mask = np.array(dark_inner) > 0
    body_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    body_arr[..., 0] = r
    body_arr[..., 1] = g
    body_arr[..., 2] = b_ch
    body_arr[..., 3] = body_mask.astype(np.uint8) * 255
    body = Image.fromarray(body_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # === Composite all ===
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(bevel)
    out.alpha_composite(dark_layer)
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
    print(f"  Preview: {PREVIEW_PNG}")


if __name__ == "__main__":
    main()
