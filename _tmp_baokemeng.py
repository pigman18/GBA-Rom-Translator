"""Render 宝可梦 with proper chunky Pokemon-style strokes.

Key fix: use ImageDraw.text() with stroke_width=N to directly draw thick strokes
instead of trying to fake them with dilation/blur.

Layered stamp:
  Layer A: Black drop shadow       (text + stroke_width=8, black, offset +3/+3)
  Layer B: White outline ring      (text + stroke_width=4, white)
  Layer C: Red gradient fill       (text + red vertical gradient via mask)
  Layer D: Subtle white highlight band on top portion of glyphs
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import os

ROOT = r"C:\code\GBA-Rom-Translator"
COMPOSE_PNG = os.path.join(ROOT, r"configs\POKEMON_RUBY_AXVJ00\tiles\0x0836D268_compose.png")
PREVIEW_PNG = os.path.join(ROOT, r"configs\POKEMON_RUBY_AXVJ00\tiles\0x0836D268_baokemeng_preview.png")

TITLE_X0, TITLE_Y0 = 6, 9
TITLE_X1, TITLE_Y1 = 195, 64
W = TITLE_X1 - TITLE_X0   # 189
H = TITLE_Y1 - TITLE_Y0   # 55

# Logo colors sampled from original
COL_SHADOW   = (16, 16, 16)        # black drop shadow
COL_OUTLINE  = (248, 248, 248)     # outer white bevel
COL_RED_BRT  = (252, 36, 44)       # bright top (slightly punchier than 248,48,56)
COL_RED_DEEP = (44, 8, 8)          # very deep red bottom (darker than 72,16,16)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simfang.ttf",
    r"C:\Windows\Fonts\simkai.ttf",
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("No CJK font available")


def make_layer(text, font_size, color, canvas_size, offset=(0, 0),
               stroke_width=0, mask_mode=False):
    """Render a text layer at the given font size, into a canvas of canvas_size (w, h).

    Returns RGBA image (or L if mask_mode=True).
    """
    cw, ch = canvas_size
    if mask_mode:
        img = Image.new("L", (cw, ch), 0)
    else:
        img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, font_size)
    if stroke_width > 0:
        d.text(offset, text, fill=color if not mask_mode else 255,
               font=f, stroke_width=stroke_width, stroke_fill=color if not mask_mode else 255)
    else:
        d.text(offset, text, fill=color if not mask_mode else 255, font=f)
    return img


def render_title(text, w, h):
    """Build the layered stamp of `text` at size (w, h)."""
    SC = 4            # oversample factor (more = smoother downsampling)
    cw, ch = w * SC, h * SC

    # Find the largest font size that fits inside an inset of (margin_px * SC)
    margin_px = 3
    margin = margin_px * SC
    bbox_inner = (cw - margin*2, ch - margin*2)

    global FONT
    FONT = find_font()

    # Auto-fit: shrink until glyph bbox fits
    fs = int(h * SC * 0.92)
    while fs > 8:
        f = ImageFont.truetype(FONT, fs)
        probe = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(probe).text((margin, margin), text, fill=255, font=f)
        bbox = probe.getbbox()
        if bbox is None:
            fs -= 1
            continue
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if bw <= bbox_inner[0] and bh <= bbox_inner[1]:
            break
        fs -= 1
    print(f"  Fit font size: {fs}px -> bbox {bw}x{bh}")

    font_obj = ImageFont.truetype(FONT, fs)

    # ---------- Layer A: black drop shadow ----------
    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(
        (margin + 4 * SC, margin + 3 * SC),
        text, fill=COL_SHADOW + (255,), font=font_obj,
        stroke_width=2 * SC, stroke_fill=COL_SHADOW + (255,)
    )

    # ---------- Layer B: dark inner ring (thin black line, gives "carved" edge) ----------
    dark_edge = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(dark_edge).text(
        (margin, margin),
        text, fill=(0, 0, 0, 255), font=font_obj,
        stroke_width=3 * SC, stroke_fill=(0, 0, 0, 255)
    )

    # ---------- Layer C: white outer bevel ----------
    # Use a thinner stroke so red dominates
    bevel = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(bevel).text(
        (margin, margin),
        text, fill=COL_OUTLINE + (255,), font=font_obj,
        stroke_width=2 * SC, stroke_fill=COL_OUTLINE + (255,)
    )

    # ---------- Layer D: red gradient fill ----------
    # Draw text + small stroke (= fattens strokes slightly) so red covers more area
    fill_mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(fill_mask).text(
        (margin, margin),
        text, fill=255, font=font_obj,
        stroke_width=1 * SC, stroke_fill=255
    )

    # Build gradient with strong contrast
    grad_arr = np.zeros((ch, cw, 3), dtype=np.float32)
    for y in range(ch):
        t = y / max(1, ch - 1)
        # 3-zone: top 25% bright highlight, mid 35% bright red, bottom 40% deep red
        if t < 0.30:
            local = t / 0.30
            r = 255 - local * 8
            g = 60 - local * 35
            b = 60 - local * 35
        elif t < 0.65:
            local = (t - 0.30) / 0.35
            r = COL_RED_BRT[0] * (1 - local * 0.3) + COL_RED_DEEP[0] * (local * 0.3) + 8
            g = COL_RED_BRT[1] * (1 - local * 0.3) + COL_RED_DEEP[1] * (local * 0.3) - 8
            b = COL_RED_BRT[2] * (1 - local * 0.3) + COL_RED_DEEP[2] * (local * 0.3) - 8
        else:
            local = (t - 0.65) / 0.35
            # Strong darkening
            r = COL_RED_BRT[0] * 0.7 * (1 - local) + COL_RED_DEEP[0] * (1 + local * 0.5)
            g = COL_RED_BRT[1] * 0.7 * (1 - local) + COL_RED_DEEP[1] * (1 + local * 0.5)
            b = COL_RED_BRT[2] * 0.7 * (1 - local) + COL_RED_DEEP[2] * (1 + local * 0.5)
        grad_arr[y, :, 0] = r
        grad_arr[y, :, 1] = g
        grad_arr[y, :, 2] = b
    grad_arr = np.clip(grad_arr, 0, 255).astype(np.uint8)
    gradient_img = Image.fromarray(grad_arr, "RGB")

    # Apply gradient through fill mask
    fill_alpha = np.array(fill_mask)
    fill_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    fill_arr[..., 0] = grad_arr[..., 0]
    fill_arr[..., 1] = grad_arr[..., 1]
    fill_arr[..., 2] = grad_arr[..., 2]
    fill_arr[..., 3] = fill_alpha
    fill = Image.fromarray(fill_arr, "RGBA")

    # ---------- Layer E: subtle white highlight band along very top ----------
    hi_mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(hi_mask).text((margin, margin), text, fill=255, font=font_obj)
    hi_arr = np.array(hi_mask).astype(np.float32)
    # Vertical fade: only top 25%
    cutoff = int(ch * 0.30)
    fade = np.zeros(ch, dtype=np.float32)
    fade[:cutoff] = np.linspace(1.0, 0.0, cutoff)
    hi_arr = hi_arr * fade.reshape(-1, 1)
    hi_img = Image.fromarray(np.clip(hi_arr, 0, 255).astype(np.uint8), "L")
    hi_img = hi_img.filter(ImageFilter.GaussianBlur(radius=3))
    hi_alpha = np.array(hi_img).astype(np.float32) / 255.0
    # Mask highlight to only appear ON the red fill
    fill_a = np.array(fill.split()[3]).astype(np.float32) / 255.0
    combo = (hi_alpha * fill_a * 180).astype(np.uint8)
    hi_rgba = np.zeros((ch, cw, 4), dtype=np.uint8)
    hi_rgba[..., :3] = COL_OUTLINE
    hi_rgba[..., 3] = combo
    highlight = Image.fromarray(hi_rgba, "RGBA")

    # ---------- COMPOSITE ----------
    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(dark_edge)
    out.alpha_composite(bevel)
    out.alpha_composite(fill)
    out.alpha_composite(highlight)

    # Downsample
    out = out.resize((w, h), Image.LANCZOS)
    return out


def main():
    img = Image.open(COMPOSE_PNG).convert("RGBA")
    arr = np.array(img).copy()

    # Clear the entire title region (the original Japanese+English+sparkle)
    arr[TITLE_Y0:TITLE_Y1, TITLE_X0:TITLE_X1] = [0, 0, 0, 0]
    base = Image.fromarray(arr, "RGBA")

    rendered = render_title("宝可梦", W, H)
    print(f"Rendered: {rendered.size}")

    base.paste(rendered, (TITLE_X0, TITLE_Y0), rendered)
    base.save(COMPOSE_PNG)
    print(f"Saved: {COMPOSE_PNG}")

    # 4x preview for human inspection
    preview = base.resize((base.size[0] * 4, base.size[1] * 4), Image.NEAREST)
    preview.save(PREVIEW_PNG)
    print(f"Preview: {PREVIEW_PNG}")


if __name__ == "__main__":
    main()
