"""Pokemon-style 宝可梦 title v2.

Key improvements over v1:
- Use the EXACT Pokemon red palette sampled from 红宝石.png (pure red, not orange-red)
- Simulate DIRECTIONAL LIGHTING (top-left highlight, bottom-right shadow) by using
  the alpha mask's gradient as a "height map" - top-left edges are bright, bottom-right
  are dark
- Use a HEAVY multi-pass stroke to give thick bold strokes (not SimHei's default thin-ish)
- Apply a spiky/angular transformation to mimic the Pokemon logo's "carved" geometry

Approach: render "宝可梦" as a thick silhouette with custom shader.
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
W = TITLE_X1 - TITLE_X0   # 189
H = TITLE_Y1 - TITLE_Y0   # 57

# Pokemon red palette (sampled from red宝石.png)
COL_BGND     = (0, 0, 0)             # outer drop shadow
COL_INNER    = (24, 4, 8)            # dark red, between bevel and fill
COL_RED_MID  = (192, 16, 16)         # mid red (shadow side)
COL_RED      = (224, 16, 16)         # main red (base)
COL_RED_HI   = (240, 16, 16)         # bright red
COL_PINK_HI  = (240, 80, 80)         # pink highlight
COL_WHITE    = (252, 252, 252)       # pure white (bevel + top highlight)

FONT = r"C:\Windows\Fonts\simhei.ttf"


def make_text_mask(text, font_size, canvas_size, margin=2, passes=3):
    """Render a thick text mask by drawing it multiple times with slight offsets.

    Returns a 1-channel L image where 255 = text body, 0 = background.
    """
    cw, ch = canvas_size
    img = Image.new("L", (cw, ch), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, font_size)
    # Draw the text 3 times at slight offsets to fatten strokes
    for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
        d.text((margin + dx, margin + dy), text, fill=255, font=f)
    return img


def directional_lighting(height_map, light_dir=(-1, -1), strength=1.0):
    """Compute lighting intensity at each pixel from a height map.

    height_map: 1-channel image, 255 = highest, 0 = lowest
    light_dir: 2-tuple (dx, dy) direction TO the light source (negative = top-left)

    Returns a float32 array of the same shape with values 0..255 representing
    the dot product of the surface normal and the light direction.
    """
    h = np.array(height_map).astype(np.float32)
    # Compute gradient (sobel-like)
    gy, gx = np.gradient(h)
    # The gradient is the negative of the surface normal
    # Normalize the gradient
    magnitude = np.sqrt(gx**2 + gy**2) + 1e-6
    nx = -gx / magnitude
    ny = -gy / magnitude
    # Compute dot product with light direction (normalized)
    lx, ly = light_dir
    l_mag = np.sqrt(lx**2 + ly**2) + 1e-6
    lx /= l_mag
    ly /= l_mag
    # Lighting = N . L
    lighting = nx * lx + ny * ly
    # Map from [-1, 1] to [0, 1]
    lighting = (lighting + 1.0) / 2.0
    return lighting


def pokemon_shade(text_mask, size):
    """Apply Pokemon-style directional shading to a text mask.

    Returns an RGBA image of given size.
    """
    w, h = size
    cw, ch = text_mask.size  # canvas size
    # Compute lighting from the height map
    lighting = directional_lighting(text_mask, light_dir=(-1, -1), strength=1.0)
    # Apply additional "fill" - the body color (mid red)
    # Lighting modulates between COL_PINK_HI (light) and COL_RED_MID (shadow)
    # Body color (mid) = COL_RED
    # Use lighting to mix between highlight and shadow

    # Generate a 3-color gradient based on lighting intensity
    #   lighting >= 0.7: COL_PINK_HI (highlight)
    #   0.4 < lighting < 0.7: COL_RED_HI (bright)
    #   0.2 < lighting < 0.4: COL_RED (main)
    #   lighting < 0.2: COL_RED_MID (shadow)

    # But we also need to add a vertical "depth" - bottom should be slightly darker
    # Add a vertical gradient as a base, then modulate with lighting
    base_grad = np.zeros((ch, cw), dtype=np.float32)
    for y in range(ch):
        t = y / max(1, ch - 1)
        base_grad[y, :] = 1.0 - t * 0.25   # 1.0 at top, 0.75 at bottom

    # Apply mask: pixels outside text should be transparent
    mask_arr = np.array(text_mask) / 255.0
    combined = lighting * base_grad

    # Map combined [0,1] to color
    r = np.where(combined > 0.6, COL_PINK_HI[0],
                 np.where(combined > 0.45, COL_RED_HI[0],
                          np.where(combined > 0.3, COL_RED[0],
                                   COL_RED_MID[0])))
    g = np.where(combined > 0.6, COL_PINK_HI[1],
                 np.where(combined > 0.45, COL_RED_HI[1],
                          np.where(combined > 0.3, COL_RED[1],
                                   COL_RED_MID[1])))
    b = np.where(combined > 0.6, COL_PINK_HI[2],
                 np.where(combined > 0.45, COL_RED_HI[2],
                          np.where(combined > 0.3, COL_RED[2],
                                   COL_RED_MID[2])))
    # Build RGBA
    arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    arr[..., 0] = r
    arr[..., 1] = g
    arr[..., 2] = b
    arr[..., 3] = (mask_arr * 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGBA")
    return img.resize((w, h), Image.LANCZOS)


def render_title(text, w, h):
    """Build the Pokemon-style title."""
    SC = 5     # higher = more detail
    cw, ch = w * SC, h * SC

    # Find font size that fits
    target_w = int(w * 0.95) * SC
    target_h = int(h * 0.92) * SC
    margin = 2 * SC
    fs = target_h
    while fs > 8:
        f = ImageFont.truetype(FONT, fs)
        probe = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(probe).text((margin, margin), text, fill=255, font=f)
        bbox = probe.getbbox()
        if bbox is None:
            fs -= 1
            continue
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if bw <= target_w and bh <= target_h:
            break
        fs -= 1
    print(f"  Font size: {fs}")

    # Build a thick mask by drawing text multiple times with offsets
    text_mask = make_text_mask(text, fs, (cw, ch), margin=margin, passes=3)

    # Erode slightly to make the "body" smaller (so we can layer bevel outside)
    inner = text_mask.filter(ImageFilter.MinFilter(3 * 2 + 1))   # 3 px shrink
    # The pixels between text_mask and inner = the bevel ring

    # Compute lighting on the inner shape (this gives the body fill)
    body = pokemon_shade(inner, (w, h))

    # White bevel: pixels in text_mask but NOT in inner = the white ring
    bevel_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    ring = (np.array(text_mask) > 0) & (np.array(inner) == 0)
    bevel_arr[ring] = COL_WHITE + (255,)
    bevel = Image.fromarray(bevel_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # Dark inner edge: small thin dark red line just inside the white ring
    dark_edge = inner.filter(ImageFilter.MaxFilter(1 * 2 + 1))  # dilate 1 px
    # But we want the OPPOSITE: inner is smaller, so dark edge is pixels in dark_edge but NOT in inner
    # Actually, for a "carved" look, the line just INSIDE the white should be dark red.
    # Take pixels that are in dark_edge (text_mask eroded by 1) but NOT in inner (text_mask eroded by 2)
    dark_inner_mask = Image.new("L", (cw, ch), 0)
    inner1 = inner.filter(ImageFilter.MinFilter(1 * 2 + 1))  # 1 px more inside
    dark_mask_arr = (np.array(dark_edge) > 0) & (np.array(inner1) == 0)
    dark_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    dark_arr[dark_mask_arr] = COL_INNER + (255,)
    dark_img = Image.fromarray(dark_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # Drop shadow: shifted copy of text_mask in black
    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    shadow_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    # Shift down-right by 4 px (high res)
    shifted = np.roll(np.array(text_mask), shift=(4 * SC, 4 * SC), axis=(0, 1))
    # Clear top and left edges that wrap around
    shifted[:4*SC, :] = 0
    shifted[:, :4*SC] = 0
    shadow_arr[shifted > 0] = (0, 0, 0, 230)
    shadow = Image.fromarray(shadow_arr, "RGBA").resize((w, h), Image.LANCZOS)

    # Composite
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(bevel)
    out.alpha_composite(dark_img)
    out.alpha_composite(body)
    return out


def main():
    img = Image.open(COMPOSE_PNG).convert("RGBA")
    arr = np.array(img).copy()
    # Clear the title region
    arr[TITLE_Y0:TITLE_Y1, TITLE_X0:TITLE_X1] = [0, 0, 0, 0]
    base = Image.fromarray(arr, "RGBA")

    rendered = render_title("宝可梦", W, H)
    print(f"  Rendered: {rendered.size}")

    base.paste(rendered, (TITLE_X0, TITLE_Y0), rendered)
    base.save(COMPOSE_PNG)
    print(f"  Saved: {COMPOSE_PNG}")

    preview = base.resize((base.size[0] * 4, base.size[1] * 4), Image.NEAREST)
    preview.save(PREVIEW_PNG)
    print(f"  Preview: {PREVIEW_PNG}")


if __name__ == "__main__":
    main()
