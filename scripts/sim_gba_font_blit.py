#!/usr/bin/env python3
"""Offline GBA Chinese font blit simulator (Linear 8+4).

Mirrors configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar/draw_glyph.c
so we can tell pack-vs-draw bugs without mGBA.

Outputs under work/font_sim/:
  01_slot_<text>.png          — decode 16x16 slots only
  02_blit_linear_<text>.png   — current C color map (15→E, 14→C)
  03_compare_grid.png         — slot | current blit | mature C/D/E map
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_chinese_font as bcf  # noqa: E402

try:
    from PIL import Image, ImageDraw

    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

BYTES_PER_GLYPH = 128
ADVANCE_PX = 12
SLOT_W = 16
SLOT_H = 16

DEFAULT_C = 1
DEFAULT_D = 2
DEFAULT_E = 3

# Remapped palette indices after blit (preview RGB)
PALETTE_RGB = {
    0: (255, 255, 255),  # transparent / unwritten
    1: (32, 32, 40),  # C — intended ink (mature)
    2: (110, 110, 130),  # D — shadow
    3: (230, 230, 240),  # E — bg / (current C misuses as ink)
}

# Raw font nybble preview (slot decode)
RAW_RGB = {
    0: (255, 255, 255),
    14: (140, 140, 155),
    15: (24, 24, 32),
}


def default_paths() -> tuple[Path, Path, Path]:
    game = "POKEMON_RUBY_AXVJ00"
    bin_path = (
        ROOT
        / "work"
        / game
        / "graphic"
        / "fonts"
        / "PokeRSFontChsNormal(0xE0000).bin"
    )
    charmap = ROOT / "configs" / game / "charmap.txt"
    if not charmap.is_file():
        charmap = ROOT / "configs" / game / "translate" / "charmap.txt"
    out_dir = ROOT / "work" / "font_sim"
    return bin_path, charmap, out_dir


def load_charmap_index(charmap_path: Path) -> dict[str, int]:
    mapping = bcf.parse_charmap(charmap_path)
    out: dict[str, int] = {}
    for idx, ch in mapping.items():
        out[ch] = idx
    return out


def decompress_slot(glyph128: bytes) -> list[int]:
    """128B TL/BL/TR/BR → 16x16 pixels (0-15). Left = high nibble."""
    if len(glyph128) != BYTES_PER_GLYPH:
        raise ValueError(f"glyph must be {BYTES_PER_GLYPH} bytes")
    pixels = [0] * (SLOT_W * SLOT_H)
    for tile_col in range(2):
        for tile_row in range(2):
            tile_idx = tile_col * 2 + tile_row
            off = tile_idx * 32
            for ty in range(8):
                py = tile_row * 8 + ty
                for tx in range(4):
                    byte = glyph128[off + ty * 4 + tx]
                    px = tile_col * 8 + tx * 2
                    pixels[py * SLOT_W + px] = (byte >> 4) & 0x0F
                    pixels[py * SLOT_W + px + 1] = byte & 0x0F
    return pixels


def get_px(tile: bytearray | bytes, x: int, y: int) -> int:
    bi = y * 4 + x // 2
    if x & 1:
        return tile[bi] & 0x0F
    return tile[bi] >> 4


def put_px(tile: bytearray, x: int, y: int, ink: int) -> None:
    bi = y * 4 + x // 2
    ink &= 0x0F
    if x & 1:
        tile[bi] = (tile[bi] & 0xF0) | ink
    else:
        tile[bi] = (tile[bi] & 0x0F) | (ink << 4)


def map_current_c(raw: int, c: int, d: int, e: int) -> int:
    """Exact draw_glyph.c line 180: 15→E, 14→C, else 0. (d unused)."""
    del d
    if raw == 15:
        return e
    if raw == 14:
        return c
    return 0


def map_mature(raw: int, c: int, d: int, e: int) -> int:
    """Mature RS CN intent: 15→ink(C), 14→shadow(D), 0→bg(E)."""
    if raw == 0:
        return e
    if raw == 15:
        return c
    if raw == 14:
        return d
    return c


def draw_glyph_tile_12(
    dest: bytearray,
    spill: bytearray | None,
    src32: bytes,
    start_pixel: int,
    width: int,
    mapper,
    c: int,
    d: int,
    e: int,
) -> None:
    """Mirror draw_glyph_tile_12 (right-edge zero fill; never fill left)."""
    gw_end = start_pixel + width
    for r in range(8):
        for col in range(width):
            dc = start_pixel + col
            if dc < 8:
                tile = dest
                px = dc
            elif spill is not None:
                tile = spill
                px = dc - 8
            else:
                continue
            raw = get_px(src32, col, r)
            put_px(tile, px, r, mapper(raw, c, d, e))
        if gw_end < 8:
            for col in range(gw_end, 8):
                put_px(dest, col, r, 0)
        if spill is not None and gw_end > 8:
            for col in range(gw_end - 8, 8):
                put_px(spill, col, r, 0)


class LinearBlitSim:
    """Linear path: tile pool + TILE_OFFSET + tilemap (upper/lower pairs)."""

    def __init__(self, n_tiles: int = 128):
        self.tiles = [bytearray(32) for _ in range(n_tiles)]
        self.chs_px = 0
        self.tile_offset = 0
        self.base_tx = 0
        # tx -> (abs_u, abs_l)
        self.tilemap: dict[int, tuple[int, int]] = {}

    def tile(self, abs_id: int) -> bytearray:
        while abs_id >= len(self.tiles):
            self.tiles.append(bytearray(32))
        return self.tiles[abs_id]

    def map_at(self, tx: int, abs_u: int, abs_l: int) -> None:
        self.tilemap[tx] = (abs_u, abs_l)

    def blit_glyph(self, glyph128: bytes, mapper, c: int, d: int, e: int) -> None:
        # C freezes startPixel for BOTH width-8 and width-4 passes
        start_pixel = self.chs_px & 7
        map_tx = self.base_tx + (self.chs_px >> 3)

        # ---- pass width 8: TL + BL ----
        if self.chs_px == 0:
            self.tile_offset = 0
        off = self.tile_offset
        abs_u = off
        abs_l = off + 1
        du = self.tile(abs_u)
        dl = self.tile(abs_l)
        if start_pixel + 8 > 8:
            du_sp = self.tile(abs_u + 2)
            dl_sp = self.tile(abs_l + 2)
        else:
            du_sp = dl_sp = None
        draw_glyph_tile_12(du, du_sp, glyph128[0x00:0x20], start_pixel, 8, mapper, c, d, e)
        draw_glyph_tile_12(dl, dl_sp, glyph128[0x20:0x40], start_pixel, 8, mapper, c, d, e)
        self.map_at(map_tx, abs_u, abs_l)
        if start_pixel + 8 > 8:
            self.map_at(map_tx + 1, abs_u + 2, abs_l + 2)
        self.tile_offset = off + 2

        self.chs_px += 8
        map_tx = self.base_tx + (self.chs_px >> 3)

        # ---- pass width 4: TR + BR (same frozen start_pixel) ----
        off = self.tile_offset
        abs_u = off
        abs_l = off + 1
        du = self.tile(abs_u)
        dl = self.tile(abs_l)
        if start_pixel + 4 > 8:
            du_sp = self.tile(abs_u + 2)
            dl_sp = self.tile(abs_l + 2)
        else:
            du_sp = dl_sp = None
        draw_glyph_tile_12(du, du_sp, glyph128[0x40:0x60], start_pixel, 4, mapper, c, d, e)
        draw_glyph_tile_12(dl, dl_sp, glyph128[0x60:0x80], start_pixel, 4, mapper, c, d, e)
        self.map_at(map_tx, abs_u, abs_l)
        if start_pixel + 4 > 8:
            self.map_at(map_tx + 1, abs_u + 2, abs_l + 2)
        self.tile_offset = off + (0 if start_pixel == 0 else 2)

        self.chs_px += 4

    def to_framebuffer(self, width_px: int, height_px: int = 16) -> list[int]:
        """Rasterize via tilemap: screen x → tx → abs upper/lower tiles."""
        fb = [0] * (width_px * height_px)
        for x in range(width_px):
            tx = self.base_tx + (x >> 3)
            px = x & 7
            pair = self.tilemap.get(tx)
            if not pair:
                continue
            abs_u, abs_l = pair
            upper = self.tile(abs_u)
            lower = self.tile(abs_l)
            for y in range(8):
                fb[y * width_px + x] = get_px(upper, px, y)
                fb[(y + 8) * width_px + x] = get_px(lower, px, y)
        return fb


def slots_row_framebuffer(glyphs: list[bytes], advance: int = ADVANCE_PX) -> tuple[list[int], int, int]:
    n = len(glyphs)
    width = max(advance * n + 4, SLOT_W)
    height = SLOT_H
    fb = [0] * (width * height)
    for i, g in enumerate(glyphs):
        pix = decompress_slot(g)
        x0 = i * advance
        for y in range(SLOT_H):
            for x in range(SLOT_W):
                dx = x0 + x
                if dx >= width:
                    continue
                v = pix[y * SLOT_W + x]
                if v:
                    fb[y * width + dx] = v
    return fb, width, height


def fb_to_rgb(
    fb: list[int],
    width: int,
    height: int,
    scale: int = 4,
    *,
    raw: bool = False,
) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for y in range(height):
        for _sy in range(scale):
            for x in range(width):
                v = fb[y * width + x]
                if raw:
                    rgb = RAW_RGB.get(v, (200, 0, 200))
                else:
                    rgb = PALETTE_RGB.get(v, (200, 0, 200))
                for _sx in range(scale):
                    out.append(rgb)
    return out


def save_image(
    path: Path,
    fb: list[int],
    width: int,
    height: int,
    scale: int = 4,
    *,
    raw: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = width * scale, height * scale
    pixels = fb_to_rgb(fb, width, height, scale, raw=raw)
    if _HAS_PIL:
        img = Image.new("RGB", (w, h), (255, 255, 255))
        img.putdata(pixels)
        draw = ImageDraw.Draw(img)
        for x in range(0, width + 1, 8):
            draw.line([(x * scale, 0), (x * scale, h - 1)], fill=(210, 210, 220))
        img.save(path)
        print(f"  wrote {path}")
        return path
    ppm = path.with_suffix(".ppm")
    with ppm.open("w", encoding="ascii") as f:
        f.write(f"P3\n{w} {h}\n255\n")
        for r, g, b in pixels:
            f.write(f"{r} {g} {b}\n")
    print(f"  wrote {ppm}")
    return ppm


def hstack_fbs(
    parts: list[tuple[list[int], int, int]], pad: int = 8
) -> tuple[list[int], int, int]:
    H = max(h for _, _, h in parts)
    W = sum(w for _, w, _ in parts) + pad * (len(parts) - 1)
    fb = [0] * (W * H)
    x0 = 0
    for src, w, h in parts:
        for y in range(h):
            for x in range(w):
                fb[y * W + (x0 + x)] = src[y * w + x]
        x0 += w + pad
    return fb, W, H


def resolve_glyphs(
    text: str,
    charmap_path: Path,
    bin_path: Path | None,
    bdf_path: Path | None,
) -> list[bytes]:
    char_to_idx = load_charmap_index(charmap_path)
    glyphs: list[bytes] = []

    if bin_path and bin_path.is_file():
        data = bin_path.read_bytes()
        for ch in text:
            if ch not in char_to_idx:
                raise KeyError(f"char {ch!r} not in charmap")
            idx = char_to_idx[ch]
            off = idx * BYTES_PER_GLYPH
            if off + BYTES_PER_GLYPH > len(data):
                raise IndexError(f"glyph index {idx} past end of bin")
            glyphs.append(data[off : off + BYTES_PER_GLYPH])
        return glyphs

    if not bdf_path or not bdf_path.is_file():
        raise FileNotFoundError("need --bin or --bdf")
    bdf_glyphs, font_ascent, _, _ = bcf.parse_bdf(bdf_path)
    for ch in text:
        if ch not in char_to_idx:
            raise KeyError(f"char {ch!r} not in charmap")
        enc = ord(ch)
        if enc in bdf_glyphs:
            rows, bw, bh, bx, by = bdf_glyphs[enc]
            ink = bcf.bdf_to_ink12(rows, bw, bh, bx, by, font_ascent)
        else:
            ink = bytearray(12 * 12)
        slot = bcf.ink12_to_slot16(ink, shadow=True)
        glyphs.append(bcf.pack_slot16_4bpp(slot))
    return glyphs


def run_blit(glyphs: list[bytes], mapper, c: int, d: int, e: int) -> tuple[list[int], int, int]:
    sim = LinearBlitSim()
    for g in glyphs:
        sim.blit_glyph(g, mapper, c, d, e)
    width = max(ADVANCE_PX * len(glyphs) + 8, 48)
    fb = sim.to_framebuffer(width, 16)
    return fb, width, 16


def main() -> None:
    bin_default, charmap_default, out_default = default_paths()
    ap = argparse.ArgumentParser(description="Simulate AXVJ Chinese Linear 8+4 blit")
    ap.add_argument("--text", default="宝可梦")
    ap.add_argument("--bin", type=Path, default=bin_default)
    ap.add_argument("--charmap", type=Path, default=charmap_default)
    ap.add_argument(
        "--bdf",
        type=Path,
        default=Path(r"C:\code\gba\fonts\ark-pixel\12px-monospaced\ark-pixel-12px-monospaced-zh_cn.bdf"),
    )
    ap.add_argument("--out-dir", type=Path, default=out_default)
    ap.add_argument("--color-c", type=int, default=DEFAULT_C)
    ap.add_argument("--color-d", type=int, default=DEFAULT_D)
    ap.add_argument("--color-e", type=int, default=DEFAULT_E)
    ap.add_argument("--scale", type=int, default=4)
    args = ap.parse_args()

    c, d, e = args.color_c, args.color_d, args.color_e
    print(f"text={args.text!r}")
    print(f"bin={args.bin} exists={args.bin.is_file()}")
    print(f"charmap={args.charmap}")
    print(f"PIL={_HAS_PIL}  colors C={c} D={d} E={e}")

    glyphs = resolve_glyphs(
        args.text,
        args.charmap,
        args.bin if args.bin.is_file() else None,
        args.bdf,
    )
    for i, ch in enumerate(args.text):
        ones = sum(1 for b in glyphs[i] for n in ((b >> 4) & 0xF, b & 0xF) if n)
        print(f"  glyph[{i}] {ch!r} non-zero-nybbles={ones}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    safe = args.text  # keep CJK in filename as plan specifies

    # 01 slot decode (raw 0/14/15)
    fb_slot, w_slot, h_slot = slots_row_framebuffer(glyphs)
    save_image(
        args.out_dir / f"01_slot_{safe}.png",
        fb_slot,
        w_slot,
        h_slot,
        args.scale,
        raw=True,
    )

    # 02 current C mapping blit
    fb_cur, w_cur, h_cur = run_blit(glyphs, map_current_c, c, d, e)
    save_image(
        args.out_dir / f"02_blit_linear_{safe}.png",
        fb_cur,
        w_cur,
        h_cur,
        args.scale,
        raw=False,
    )

    # mature mapping
    fb_mat, w_mat, h_mat = run_blit(glyphs, map_mature, c, d, e)

    # 03 compare — remapped for blit panels; slot stays raw values but we
    # convert slot to a common display by mapping 15→1,14→2 for stacking RGB.
    def slot_as_display(fb: list[int]) -> list[int]:
        out = []
        for v in fb:
            if v == 15:
                out.append(1)
            elif v == 14:
                out.append(2)
            else:
                out.append(0)
        return out

    fb_cmp, w_cmp, h_cmp = hstack_fbs(
        [
            (slot_as_display(fb_slot), w_slot, h_slot),
            (fb_cur, w_cur, h_cur),
            (fb_mat, w_mat, h_mat),
        ],
        pad=12,
    )
    cmp_path = args.out_dir / "03_compare_grid.png"
    if _HAS_PIL:
        scale = args.scale
        header = 28
        img = Image.new("RGB", (w_cmp * scale, h_cmp * scale + header), (240, 240, 245))
        body = Image.new("RGB", (w_cmp * scale, h_cmp * scale))
        body.putdata(fb_to_rgb(fb_cmp, w_cmp, h_cmp, scale, raw=False))
        img.paste(body, (0, header))
        draw = ImageDraw.Draw(img)
        labels = [
            ("01 slot", w_slot),
            ("02 current (15→E,14→C)", w_cur),
            ("03 mature (15→C,14→D,0→E)", w_mat),
        ]
        x = 4
        for lab, ww in labels:
            draw.text((x, 6), lab, fill=(20, 20, 30))
            x += ww * scale + 12 * scale
        img.save(cmp_path)
        print(f"  wrote {cmp_path}")
    else:
        save_image(cmp_path, fb_cmp, w_cmp, h_cmp, args.scale)

    def nonzero_ratio(fb: list[int]) -> float:
        return sum(1 for v in fb if v) / max(len(fb), 1)

    print("--- verdict hint ---")
    print(f"slot nonzero ratio:    {nonzero_ratio(fb_slot):.3f}")
    print(f"current blit ratio:    {nonzero_ratio(fb_cur):.3f}")
    print(f"mature blit ratio:     {nonzero_ratio(fb_mat):.3f}")
    print(f"out_dir={args.out_dir}")
    print("If 01 readable but 02 looks wrong → draw/color map; if 01 bad → pack/index.")
    print("If 03 readable and 02 not → fix C/D/E map in draw_glyph.c next.")


if __name__ == "__main__":
    main()
