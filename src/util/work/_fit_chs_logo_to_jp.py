"""Fit configs CHS title logo into JP tilemap-safe cells.

Strategy (no carving ink):
  1. Restore art from bak / current compose crop
  2. Try translate within JP logo box
  3. If still conflicts tilemap index 0, shrink and retry
  4. Prefer largest scale, then closest to original place (24,8)

JP export: util/works/.../0x0836D268_compose.png
CHS target: configs/.../tiles/0x0836D268_compose.png
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "util"))
from tiles_patcher import gba_address_to_offset, lz77_decompress  # noqa: E402

JP = ROOT / "src/util/works/POKEMON_RUBY_AXVJ00/tiles/0x0836D268_compose.png"
CHS = ROOT / "configs/POKEMON_RUBY_AXVJ00/tiles/0x0836D268_compose.png"
BAK = CHS.parent / "bak"
ORIGIN = ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba"
JP_LOGO_BOX = (10, 8, 191, 64)
ORIG_PLACE = (24, 8)


def has_idx0_conflict(im: Image.Image, map_data: bytes) -> bool:
    for row in range(32):
        for col in range(32):
            if map_data[row * 32 + col] != 0:
                continue
            t = im.crop((col * 8, row * 8, col * 8 + 8, row * 8 + 8))
            for p in t.getdata():
                if p[3] > 0 and (p[0] | p[1] | p[2]) != 0:
                    return True
    return False


def find_fit(
    content: Image.Image, canvas_size: tuple[int, int], map_data: bytes
) -> tuple[float, int, int, int, int]:
    """Return (scale, x, y, nw, nh). Largest scale, then nearest ORIG_PLACE."""
    x0, y0, x1, y1 = JP_LOGO_BOX
    tw, th = x1 - x0, y1 - y0
    ox, oy = ORIG_PLACE

    for scale_i in range(100, 50, -1):
        s = scale_i / 100.0
        nw = max(1, int(round(content.width * s)))
        nh = max(1, int(round(content.height * s)))
        if nw > tw or nh > th:
            continue
        scaled = content.resize((nw, nh), Image.Resampling.NEAREST)
        cands: list[tuple[int, int, int]] = []
        for y in range(y0, y1 - nh + 1):
            for x in range(x0, x1 - nw + 1):
                cands.append((abs(x - ox) + abs(y - oy), x, y))
        cands.sort()
        for _dist, x, y in cands:
            out = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            out.alpha_composite(scaled, (x, y))
            if not has_idx0_conflict(out, map_data):
                return s, x, y, nw, nh
    raise RuntimeError("no translate/scale fit without tilemap index-0 conflict")


def main() -> None:
    assert JP.is_file(), f"missing JP export: {JP}"
    assert ORIGIN.is_file(), ORIGIN

    # Prefer last good bak (pre-carve); else current CHS
    src_path = CHS
    preferred = BAK / "0x0836D268_compose.202608082311.png"
    if preferred.is_file():
        src_path = preferred
        print("source", preferred.name, "(pre-carve bak)")
    else:
        assert CHS.is_file(), CHS
        print("source", CHS.name)

    rom = ORIGIN.read_bytes()
    map_data = lz77_decompress(
        rom[gba_address_to_offset(0x0836D030) :], swap=True
    )

    src = Image.open(src_path).convert("RGBA")
    bb = src.getbbox()
    assert bb
    content = src.crop(bb)

    s, x, y, nw, nh = find_fit(content, src.size, map_data)
    print(f"fit scale={s} pos=({x},{y}) size=({nw},{nh})")

    scaled = content.resize((nw, nh), Image.Resampling.NEAREST)
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    out.alpha_composite(scaled, (x, y))
    assert not has_idx0_conflict(out, map_data)

    BAK.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M")
    bak_path = BAK / f"{CHS.stem}.{ts}{CHS.suffix}"
    if bak_path.exists():
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        bak_path = BAK / f"{CHS.stem}.{ts}{CHS.suffix}"
    if CHS.is_file():
        shutil.copy2(CHS, bak_path)
        print("bak", bak_path.name)

    out.save(CHS)
    print("saved", CHS, "bbox", out.getbbox())


if __name__ == "__main__":
    main()
