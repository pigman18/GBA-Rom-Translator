#!/usr/bin/env python3
"""对指定图形块，静态解析其真实调色板与 bpp。

原理：RSE 图形加载时，引用该块的代码函数字面量池中带调色板数据地址
（或指向调色板数据的 CompressedSpritePalette 结构体）。本脚本：
1. 找所有指向图形块的指针（代码/数据）
2. 数据指针继续追一级（结构体 → 引用它的代码）
3. 从代码函数字面量池中筛出"LZ77 解压后为有效 GBA555 且首色黑"的块，
   或指向这种块的指针 → 即为调色板候选
4. 调色板字节数 → 推断 bpp（32B=1bank/4bpp, 96B=3bank/4bpp, 512B=16bank/8bpp）

用法: python _find_palettes.py <rom> <gba_addr> [更多地址...]
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiles_patcher import (
    detect_lz77, lz77_decompress, _is_valid_gba555, _auto_palette_size,
    _detect_bpp, find_lz77_size,
)

CODE_LO, CODE_HI = 0x08000000, 0x081BFFFF


def is_code(addr: int) -> bool:
    return CODE_LO <= addr <= CODE_HI


def lz_pal_candidate(rom, off) -> tuple | None:
    """off 处若是 LZ77 且解压为有效 GBA555 调色板（首色黑），返回 (bytes, swap)。"""
    if off + 4 > len(rom) or rom[off] != 0x10:
        return None
    dsize = rom[off + 1] | (rom[off + 2] << 8) | (rom[off + 3] << 16)
    if dsize not in (32, 64, 96, 128, 160, 192, 224, 256, 512):
        return None
    comp = detect_lz77(rom, off)
    if comp == "none":
        return None
    dec = lz77_decompress(rom[off:], swap=(comp == "lz77_swap"))
    if len(dec) != dsize or dec[0] != 0 or dec[1] != 0:
        return None
    if not _is_valid_gba555(dec):
        return None
    return dec, comp


def raw_pal_candidate(rom, off) -> tuple | None:
    """off 处若是裸 GBA555（首色黑，1-16 bank）。"""
    if off + 32 > len(rom) or rom[off] != 0 or rom[off + 1] != 0:
        return None
    chunk = rom[off:off + 512]
    sz = _auto_palette_size(chunk)
    if sz < 32:
        return None
    if not _is_valid_gba555(chunk[:sz]):
        return None
    return chunk[:sz], "none"


def literals_in_range(rom, ref_addr, span=0x500) -> list[int]:
    """ref_addr 所在函数的字面量池：ref±span 内所有 0x08xxxxxx 小端值。"""
    off = ref_addr - 0x08000000
    lo = max(0, off - span)
    hi = min(len(rom) - 4, off + span)
    out = []
    for i in range(lo, hi, 2):
        v = struct.unpack("<I", rom[i:i + 4])[0]
        if 0x08000000 <= v < 0x0A000000:
            out.append(v)
    return out


def find_refs(rom, target_gba) -> list[int]:
    b = struct.pack("<I", target_gba)
    refs = []
    for i in range(0, len(rom) - 4, 2):
        if rom[i:i + 4] == b:
            refs.append(i + 0x08000000)
    return refs


def analyze(rom, addr: int) -> dict:
    out = {"addr": addr, "palettes": [], "code_refs": [], "literals": []}
    refs = find_refs(rom, addr)
    # 收集代码引用 + 二级数据引用
    code_refs = [r for r in refs if is_code(r)]
    data_refs = [r for r in refs if not is_code(r)]
    lits = set()
    for r in code_refs:
        out["code_refs"].append(r)
        lits.update(literals_in_range(rom, r))
    # 数据引用（结构体）→ 追一级找代码
    for r in data_refs[:4]:
        r2 = find_refs(rom, r)
        for rr in r2:
            if is_code(rr):
                out["code_refs"].append(rr)
                lits.update(literals_in_range(rom, rr))
    out["literals"] = sorted(lits)
    # 从字面量池筛调色板
    seen = set()
    for lit in sorted(lits):
        if lit in seen:
            continue
        seen.add(lit)
        toff = lit - 0x08000000
        if toff < 0 or toff >= len(rom):
            continue
        cand = lz_pal_candidate(rom, toff) or raw_pal_candidate(rom, toff)
        if cand:
            dec, comp = cand
            banks = len(dec) // 32
            out["palettes"].append(
                {"addr": lit, "bytes": len(dec), "banks": banks, "comp": comp,
                 "bpp_hint": "8bpp" if banks >= 16 else "4bpp"})
    return out


def main():
    rom_path = Path(sys.argv[1])
    rom = rom_path.read_bytes()
    for a in sys.argv[2:]:
        addr = int(a, 16) if a.lower().startswith("0x") else int(a)
        res = analyze(rom, addr)
        print(f"=== 0x{addr:08X} ===")
        if res["palettes"]:
            for p in res["palettes"]:
                print(f"  调色板 0x{p['addr']:08X} ({p['bytes']}B, {p['banks']}bank, {p['comp']}) → {p['bpp_hint']}")
        else:
            print("  未找到调色板")
        print(f"  代码引用: {[hex(x) for x in res['code_refs'][:6]]}")
        if not res["palettes"] and res["literals"]:
            print(f"  字面量: {[hex(x) for x in res['literals'][:12]]}")


if __name__ == "__main__":
    main()
