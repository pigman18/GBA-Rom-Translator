#!/usr/bin/env python3
"""扫描 ROM 中全部 LZ77 图形块，输出候选资源表（用于补充 tiles.presets）。

用法: python _scan_tiles.py <rom> [--min-dst N]
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiles_patcher import (  # noqa: E402
    lz77_decompress, find_lz77_size, detect_lz77, _is_valid_gba555,
    _detect_bpp, _infer_sprite_size, _auto_palette_size,
)


def scan(rom: bytes, min_dst: int = 64):
    n = len(rom)
    out = []
    off = 0
    # 4 字节对齐扫描 LZ77 头
    for off in range(0, n - 4, 4):
        if rom[off] != 0x10:
            continue
        dst_size = rom[off + 1] | (rom[off + 2] << 8) | (rom[off + 3] << 16)
        if dst_size < min_dst or dst_size > 0x30000:
            continue
        comp = detect_lz77(rom, off)
        if comp == "none":
            continue
        csize = find_lz77_size(rom, off)
        out.append((off, csize, dst_size, comp))
    return out


def pal_near(rom: bytes, off: int, span: int = 0x8000):
    """在 off±span 内找调色板（raw GBA555，首色黑）。"""
    start = max(0, off - span)
    end = min(len(rom), off + span)
    best = None
    for i in range(start, end - 32, 2):
        if rom[i] != 0 or rom[i + 1] != 0:
            continue
        chunk = rom[i:i + 512]
        sz = _auto_palette_size(chunk)
        if sz >= 32:
            d = abs(i - off)
            if best is None or d < best[0]:
                best = (d, i, sz)
    return best


def main():
    rom_path = Path(sys.argv[1])
    rom = rom_path.read_bytes()
    blocks = scan(rom)
    print(f"LZ77 块数: {len(blocks)}")
    print(f"{'offset':>8} {'addr':>10} {'csize':>7} {'dsize':>7} {'comp':>9} {'bpp':>3} {'w':>3} {'h':>3} {'cnt':>4} {'pal':>10} {'pal_sz':>6}")
    for off, csize, dsize, comp in blocks:
        dec = lz77_decompress(rom[off:], swap=(comp == "lz77_swap"))
        bpp = _detect_bpp(dec)
        w, h, cnt = _infer_sprite_size(dsize, bpp)
        pb = pal_near(rom, off)
        pal_s = f"0x{pb[1]+0x08000000:08X}" if pb else "-"
        pal_sz = pb[2] if pb else 0
        print(f"{off:>8} 0x{off+0x08000000:08X} {csize:>7} {dsize:>7} {comp:>9} {bpp:>3} {w:>3} {h:>3} {cnt:>4} {pal_s:>10} {pal_sz:>6}")


if __name__ == "__main__":
    main()
