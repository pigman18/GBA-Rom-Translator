"""12px text renderer · String-Page prototype (design proof, not a ROM patch).

This script proves the three load-bearing claims of docs/DESIGN_TEXT_12PX_PAGE.md:

  C1  A whole Chinese string can be rasterised OFFLINE into an ordered list of
      8x16 GBA tile columns; the 12px phase (12 % 8 == 4) is baked into the
      column pixels, so the runtime needs no pixel cursor at all.
  C2  Replaying those columns through a tilemap reproduces the ideal 12px
      rendering PIXEL FOR PIXEL (including the low-nibble = left pixel rule).
  C3  Column ownership can be precomputed: every column is emitted exactly
      once, at the last character that touches it. No allocator, no recycle,
      no "row segment", no runtime phase table.

Run:  C:/Python314/python.exe scripts/research/string_page/page_prototype.py
Out:  work/string_page/page_sample.png, page_report.json
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
CHARMAP = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "charmap.txt"
OUT = ROOT / "work" / "string_page"

FONT_ROM_ADDR = 0x09000000
ROM_BASE = 0x08000000
GLYPH_BYTES = 128
ADVANCE = 12
INK_W, INK_H, PAD_TOP = 12, 12, 3
TILE_W = 8
COL_BYTES = 64  # upper 32B + lower 32B


def _lead_adjust(lead: int) -> int:
    """scripts/build_chinese_font.py: lead 0x06 / 0x1B are skipped."""
    adj = lead - 1
    if lead >= 6:
        adj -= 1
    if lead >= 0x1B:
        adj -= 1
    return adj


def load_charmap_index():
    """glyph code -> slot index inside FontChsNormal.

    The font is NOT laid out in charmap file order. build_chinese_font.py uses
    ``glyph_index(lead, trail) = lead_adjust(lead)*256 + trail``.
    """
    mapping, chars = {}, []
    for line in CHARMAP.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^\s*([0-9A-Fa-f]+)\s*=\s*(\S*)", line)
        if not m or not m.group(2):
            continue
        v = int(m.group(1), 16)
        if v <= 0xFF:
            continue
        lead, trail = (v >> 8) & 0xFF, v & 0xFF
        idx = _lead_adjust(lead) * 256 + trail
        if idx >= 7168:
            continue
        mapping[v] = idx
        chars.append(m.group(2))
    return mapping, chars


def glyph_pixel(font: bytes, idx: int, x: int, y: int) -> int:
    """Read one 4bpp pixel out of a 16x16 / 128B glyph slot (TL BL TR BR)."""
    base = idx * GLYPH_BYTES
    if x < 8 and y < 8:
        off = base + y * 4 + (x >> 1)
    elif x < 8:
        off = base + 32 + (y - 8) * 4 + (x >> 1)
    elif y < 8:
        off = base + 64 + y * 4 + ((x - 8) >> 1)
    else:
        off = base + 96 + (y - 8) * 4 + ((x - 8) >> 1)
    if off >= len(font):
        return 0
    # GBA 4bpp: LOW nibble is the LEFT pixel. Getting this backwards is the
    # direct cause of the "two characters drawn on top of each other" artefact.
    return (font[off] >> (4 * (x & 1))) & 0xF


def set_column_pixel(col: bytearray, y: int, p: int, v: int) -> None:
    off = (y if y < 8 else y - 8) * 4 + (p >> 1) + (0 if y < 8 else 32)
    col[off] |= (v & 0xF) << (4 * (p & 1))


def get_column_pixel(col: bytes, y: int, p: int) -> int:
    off = (y if y < 8 else y - 8) * 4 + (p >> 1) + (0 if y < 8 else 32)
    return (col[off] >> (4 * (p & 1))) & 0xF


def rasterise_page(font: bytes, cmap: dict[int, int], codes: list[int]):
    """Whole string -> list of 64B tile columns + per-character column owners."""
    ncols = (ADVANCE * len(codes) + TILE_W - 1) // TILE_W
    grid = [[[0] * TILE_W for _ in range(16)] for _ in range(ncols)]
    for k, code in enumerate(codes):
        idx = cmap.get(code, 0)
        X = ADVANCE * k
        for gy in range(INK_H):
            for gx in range(INK_W):
                v = glyph_pixel(font, idx, gx, PAD_TOP + gy)
                if not v:
                    continue
                px = X + gx
                c, p = px >> 3, px & 7
                if c < ncols:
                    grid[c][PAD_TOP + gy][p] = v

    columns = []
    for c in range(ncols):
        b = bytearray(COL_BYTES)
        for y in range(16):
            for p in range(TILE_W):
                v = grid[c][y][p]
                if v:
                    set_column_pixel(b, y, p, v)
        columns.append(bytes(b))

    # A column is emitted at the LAST character that inks it. This keeps the
    # typewriter effect honest and guarantees sum(owned) == ncols.
    owner = [-1] * ncols
    for k in range(len(codes)):
        lo = (ADVANCE * k) >> 3
        hi = (ADVANCE * k + INK_W - 1) >> 3
        for c in range(lo, min(hi + 1, ncols)):
            owner[c] = k
    owned = [[] for _ in codes]
    for c, k in enumerate(owner):
        if k >= 0:
            owned[k].append(c)
    return columns, owned, owner


def ideal_bitmap_fast(font: bytes, cmap: dict[int, int], codes: list[int]):
    """Ground truth: draw glyphs straight at 12px pitch, no tiles involved."""
    w = ADVANCE * len(codes)
    rows = [[0] * w for _ in range(16)]
    for k, code in enumerate(codes):
        idx = cmap.get(code, 0)
        for gy in range(INK_H):
            for gx in range(INK_W):
                v = glyph_pixel(font, idx, gx, PAD_TOP + gy)
                if v:
                    rows[PAD_TOP + gy][ADVANCE * k + gx] = v
    return rows


def page_bitmap(columns):
    """Replay tile columns through a tilemap: column c occupies screen px 8c..8c+7."""
    w = TILE_W * len(columns)
    rows = [[0] * w for _ in range(16)]
    for c, col in enumerate(columns):
        for y in range(16):
            for p in range(TILE_W):
                rows[y][TILE_W * c + p] = get_column_pixel(col, y, p)
    return rows


def save_png(rows_a, rows_b, path: Path, scale: int = 6):
    from PIL import Image, ImageDraw

    h = len(rows_a) + len(rows_b) + 6
    w = max(len(rows_a[0]), len(rows_b[0]))
    img = Image.new("RGB", (w * scale, h * scale), (232, 236, 240))
    d = ImageDraw.Draw(img)
    for band, rows in ((0, rows_a), (len(rows_a) + 6, rows_b)):
        for y, row in enumerate(rows):
            for x, v in enumerate(row):
                if v:
                    d.rectangle(
                        [x * scale, (band + y) * scale,
                         (x + 1) * scale - 1, (band + y + 1) * scale - 1],
                        fill=(28, 32, 38),
                    )
    img.save(path)


def scan_rom_segments(rom: bytes, valid: set[int]):
    segs, cur, i, N = [], [], 0, len(rom)
    while i < N - 4:
        if rom[i] == 0xF7 and rom[i + 1] == 0x00:
            cur.append((rom[i + 2] << 8) | rom[i + 3])
            i += 4
        else:
            if cur:
                segs.append(cur)
                cur = []
            i += 1
    if cur:
        segs.append(cur)
    return sorted({tuple(s) for s in segs
                   if len(s) >= 2 and all(c in valid for c in s)})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rom = ROM.read_bytes()
    font = rom[FONT_ROM_ADDR - ROM_BASE: FONT_ROM_ADDR - ROM_BASE + 7168 * GLYPH_BYTES]
    cmap, chars = load_charmap_index()
    print(f"charmap 2-byte codes: {len(cmap)}; font bytes: {len(font)}")

    # ---- C1/C2: a real product string -------------------------------------
    sample_text = "妙蛙种子"
    rev = {c: v for v, c in zip(cmap.keys(), chars)}
    sample_codes = [rev[c] for c in sample_text]
    print(f"sample {sample_text!r} codes: {[hex(c) for c in sample_codes]}")

    columns, owned, owner = rasterise_page(font, cmap, sample_codes)
    ideal = ideal_bitmap_fast(font, cmap, sample_codes)
    replay = page_bitmap(columns)
    w = len(ideal[0])
    diff = sum(1 for y in range(16) for x in range(w)
               if bool(ideal[y][x]) != bool(replay[y][x]))
    print(f"C1 columns={len(columns)} owner={owner} per-char={owned}")
    print(f"C2 pixel mismatch ideal-vs-page = {diff}")
    assert diff == 0, "page replay must equal ideal 12px rendering"
    assert sum(len(o) for o in owned) == len(columns)
    assert [c for o in owned for c in o] == list(range(len(columns)))
    save_png(ideal, replay, OUT / "page_sample.png")

    # ---- C3: capacity over every real string in the product ROM ------------
    t = time.time()
    segs = scan_rom_segments(rom, set(cmap))
    lens, unique_cols = [], set()
    for s in segs:
        cols, _, _ = rasterise_page(font, cmap, list(s))
        lens.append(len(cols))
        unique_cols.update(cols)
    print(f"strings={len(segs)} chars={sum(len(s) for s in segs)} "
          f"distinct={len({c for s in segs for c in s})}")
    print(f"columns: max={max(lens)} avg={sum(lens)/len(lens):.2f} "
          f"p99={sorted(lens)[int(len(lens)*0.99)]}")
    print(f"GLOBAL distinct column contents={len(unique_cols)} "
          f"(-> a global static atlas is IMPOSSIBLE: {len(unique_cols)*2} tiles)")

    # See docs/DESIGN_TEXT_12PX_PAGE.md 2.3. 24 columns covers the measured
    # max of 23 columns (100%), so no offline splitting is needed.
    # 12 zones x 24 cols x 2 tiles = 576 slots. PHYS tile numbers are relative
    # to tpl[0x0C] VRAM base (10-bit tilemap entry), not bounded by 512.
    zone_cols = 24
    zones = 12
    budget = zones * zone_cols * 2
    need_split = sum(1 for n in lens if n > zone_cols)
    print(f"per-window budget: {zones} zones x {zone_cols} cols x 2 = {budget} tiles; "
          f"coverage={100*(1-need_split/len(lens)):.2f}%")
    print(f"strings exceeding one zone (need split): {need_split} / {len(lens)}")

    report = {
        "sample": sample_text,
        "sample_columns": len(columns),
        "sample_owner": owner,
        "sample_per_char_columns": owned,
        "pixel_mismatch": diff,
        "strings": len(segs),
        "distinct_chars": len({c for s in segs for c in s}),
        "columns_max": max(lens),
        "columns_p99": sorted(lens)[int(len(lens) * 0.99)],
        "columns_avg": round(sum(lens) / len(lens), 2),
        "zone_columns": zone_cols,
        "strings_needing_offline_split": need_split,
        "global_distinct_column_contents": len(unique_cols),
        "global_atlas_tiles_needed": len(unique_cols) * 2,
        "per_window_page_budget_tiles": budget,
        "elapsed_s": round(time.time() - t, 1),
    }
    (OUT / "page_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"elapsed {report['elapsed_s']}s -> {OUT/'page_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
