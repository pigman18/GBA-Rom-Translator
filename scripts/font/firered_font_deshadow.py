#!/usr/bin/env python3
"""FireRed glyph deshadow helpers.

FireRed dump (`work/_probe/font_final/glyphs.npy`) uses palette nibbles:
  10 = background (majority)
  12 = ink (foreground)
  1  = shadow / outline (almost always adjacent to ink)

AXVJ product path is ink-only (no ShadowedFont bg OR). Export BDF must
drop shadow before packing.
"""
from __future__ import annotations

import numpy as np

# Normal FireRed dump (font_final)
BG = 10
INK = 12
SHADOW = 1

# Small FireRed dump (smallfont_X): 1=bg, 2=mid/shadow, 3=ink
SMALL_BG = 1
SMALL_INK = 3
SMALL_SHADOW = 2


def deshadow_matrix(
    m: np.ndarray,
    *,
    mode: str = "ink_only",
    ink: int = INK,
    shadow: int = SHADOW,
) -> np.ndarray:
    """Return binary ink mask (1=ink, 0=empty), shape HxW.

    mode:
      ink_only — keep nibble==ink only (recommended)
      drop_adj — keep ink; keep shadow only if no adjacent ink
    """
    m = np.asarray(m, dtype=np.uint8)
    if mode == "ink_only":
        return (m == ink).astype(np.uint8)
    if mode == "drop_adj":
        out = (m == ink).astype(np.uint8)
        ys, xs = np.where(m == shadow)
        h, w = m.shape
        for y, x in zip(ys.tolist(), xs.tolist()):
            near = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and m[ny, nx] == ink:
                        near = True
                        break
                if near:
                    break
            if not near:
                out[y, x] = 1
        return out
    raise ValueError(f"unknown deshadow mode: {mode}")


def ink_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Return (x0, y0, x1, y1) inclusive bbox, or None if empty."""
    ys, xs = np.where(mask != 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def mask_to_rows(mask: np.ndarray, width: int = 16) -> list[int]:
    """Pack binary mask rows into BDF hex row ints (MSB = leftmost).

    Each row becomes enough bytes to cover ``width`` bits (ceil(width/8)*8).
    """
    h, w = mask.shape
    bw = (width + 7) // 8
    rows: list[int] = []
    for y in range(h):
        v = 0
        for x in range(min(w, width)):
            if mask[y, x]:
                # bit position within padded width
                bit = (bw * 8 - 1) - x
                # Actually BDF: leftmost pixel = high bit of first byte
                byte_i = x // 8
                bit_i = 7 - (x % 8)
                # accumulate per-byte then join
                pass
        # rebuild cleanly
        buf = bytearray(bw)
        for x in range(min(w, width)):
            if mask[y, x]:
                buf[x // 8] |= 0x80 >> (x % 8)
        # store as single int for convenience when bw==2 (16px)
        n = 0
        for b in buf:
            n = (n << 8) | b
        rows.append(n)
    return rows


def mask_to_bdf_hex_rows(mask: np.ndarray, width: int = 16) -> list[str]:
    """BDF BITMAP lines for a binary mask (1=ink)."""
    h, w = mask.shape
    bw = max(1, (width + 7) // 8)
    lines: list[str] = []
    for y in range(h):
        buf = bytearray(bw)
        for x in range(min(w, width)):
            if x < w and mask[y, x]:
                buf[x // 8] |= 0x80 >> (x % 8)
        lines.append(buf.hex().upper())
    return lines
