#!/usr/bin/env python3
"""生成 1bpp 位流测试字库（pokeE 格式，charmap 序）。

来源优先级（每槽位）：
  1. pokeE gba_chs_font_11x11/9x9.bin（GB2312 汉字序 6763 字，已实测验证：
     「一/乙/屹」逐位渲染比对吻合）——char ∈ GB2312 汉字时直接搬位流；
  2. 自有 4bpp unshadow 库（Normal/Small）阈值化派生（nibble 0xF=墨），
     裁到 11×11 / 9×9——覆盖 GB2312 没有的符号（§※「」等）；
  3. 空槽全零。

位流格式（pokeE Convert1bppTo2bpp 语义，反汇编钉死）：
  每行 width 位 MSB-first 连续排布（行间无填充），大库 11 行×11bit→16B 步进，
  小库 9 行×9bit→11B 步进；渲染时行偏移 line_off（大 1 / 小 2）。
  墨迹左对齐；阴影由运行时转换生成（右下 +1px，重叠去除）。

输出（_unshadow 命名 → 流水线标点补丁自动跳过）：
  graphic/fonts/PokeRSFontChsBig1Bpp_unshadow(0x1C000).bin   7168×16B
  graphic/fonts/PokeRSFontChsSmall1Bpp_unshadow(0x13400).bin 7168×11B
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = "POKEMON_RUBY_AXVJ00"
SLOT_N = 7168
BIG_W, SMALL_W = 11, 9
BIG_ROWS, SMALL_ROWS = 11, 9

POKE_BIG = ROOT / "tools/Pokemon_GBA_Font_Patch/pokeE/graphics/fonts/gba_chs_font_11x11.bin"
POKE_SMALL = ROOT / "tools/Pokemon_GBA_Font_Patch/pokeE/graphics/fonts/gba_chs_font_9x9.bin"
CHARMAP = ROOT / "work" / GAME / "charmap.txt"
OUR_NORMAL = ROOT / "work" / GAME / "graphic/fonts/PokeRSFontChsNormal_unshadow(0xE0000).bin"
OUR_SMALL = ROOT / "work" / GAME / "graphic/fonts/PokeRSFontChsSmall_unshadow(0xE0000).bin"
OUT_DIR = ROOT / "graphic" / "fonts"
WORK_FONTS = ROOT / "work" / GAME / "graphic" / "fonts"


def _load_build_chinese_font():
    p = ROOT / "scripts" / "build_chinese_font.py"
    spec = importlib.util.spec_from_file_location("bcf", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gb2312_hanzi_map() -> dict[str, int]:
    """char → GB2312 汉字序 idx（区16-87 位1-94，pokeE bin 实测即此序）。"""
    out: dict[str, int] = {}
    for q in range(16, 88):
        for w in range(1, 95):
            try:
                ch = bytes([q + 0xA0, w + 0xA0]).decode("gb2312")
            except UnicodeDecodeError:
                continue
            out.setdefault(ch, (q - 16) * 94 + (w - 1))
    return out


def cell_ink_bits(bin_data: bytes, slot: int, *, big: bool) -> list[int]:
    """自有 4bpp 库槽位 → 16×16 墨迹位图（行优先 16 int，bit0=最左列）。"""
    base = slot * 128
    rows = []
    for r in range(16):
        v = 0
        for x in range(16):
            tile = (0 if r < 8 else 0x20) + (0 if x < 8 else 0x40)
            b = bin_data[base + tile + (r % 8) * 4 + (x >> 1)]
            nib = (b >> (0 if x % 2 == 0 else 4)) & 0xF
            if nib:
                v |= 1 << x
        rows.append(v)
    return rows


def derive_from_4bpp(bin_data: bytes, slot: int, *, width: int, rows: int) -> bytes | None:
    """4bpp 墨迹裁 (width×rows)：找首个墨行起往下取 rows，列取最左 width。"""
    bits = cell_ink_bits(bin_data, slot, big=width == BIG_W)
    first = next((r for r, v in enumerate(bits) if v), None)
    if first is None:
        return None
    first = max(0, first - 1)  # 上留 1 行呼吸位（对齐 pokeE 行偏移观感）
    acc = 0
    nb = 0
    out = bytearray()
    for r in range(rows):
        v = bits[first + r] if first + r < 16 else 0
        for c in range(width):
            bit = (v >> c) & 1
            acc = (acc << 1) | bit
            nb += 1
            if nb == 8:
                out.append(acc)
                acc = 0
                nb = 0
    if nb:
        out.append(acc << (8 - nb))
    stride = (width * rows + 7) // 8
    out.extend(b"\x00" * (stride - len(out)))
    return bytes(out)


def main() -> None:
    bcf = _load_build_chinese_font()
    cm = bcf.parse_charmap(CHARMAP)
    gb = gb2312_hanzi_map()
    poke_big = POKE_BIG.read_bytes()
    poke_small = POKE_SMALL.read_bytes()
    our_normal = OUR_NORMAL.read_bytes() if OUR_NORMAL.exists() else None
    our_small = OUR_SMALL.read_bytes() if OUR_SMALL.exists() else None

    big_stride = (BIG_W * BIG_ROWS + 7) // 8   # 16
    small_stride = (SMALL_W * SMALL_ROWS + 7) // 8  # 11
    big_out = bytearray(SLOT_N * big_stride)
    small_out = bytearray(SLOT_N * small_stride)
    stat = {"pokee": 0, "derived": 0, "blank": 0}

    for slot in range(SLOT_N):
        ch = cm.get(slot)
        if not ch:
            stat["blank"] += 1
            continue
        gi = gb.get(ch)
        if gi is not None and gi * big_stride + big_stride <= len(poke_big):
            big_out[slot * big_stride:(slot + 1) * big_stride] = poke_big[
                gi * big_stride:(gi + 1) * big_stride]
            small_out[slot * small_stride:(slot + 1) * small_stride] = poke_small[
                gi * small_stride:(gi + 1) * small_stride]
            stat["pokee"] += 1
            continue
        d_big = derive_from_4bpp(our_normal, slot, width=BIG_W, rows=BIG_ROWS) if our_normal else None
        d_small = derive_from_4bpp(our_small, slot, width=SMALL_W, rows=SMALL_ROWS) if our_small else None
        if d_big:
            big_out[slot * big_stride:(slot + 1) * big_stride] = d_big
        if d_small:
            small_out[slot * small_stride:(slot + 1) * small_stride] = d_small
        stat["derived" if (d_big or d_small) else "blank"] += 1

    big_name = f"PokeRSFontChsBig1Bpp_unshadow(0x{SLOT_N * big_stride:X}).bin"
    small_name = f"PokeRSFontChsSmall1Bpp_unshadow(0x{SLOT_N * small_stride:X}).bin"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_FONTS.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / big_name).write_bytes(big_out)
    (OUT_DIR / small_name).write_bytes(small_out)
    (WORK_FONTS / big_name).write_bytes(big_out)
    (WORK_FONTS / small_name).write_bytes(small_out)
    print(f"charmap slots with char: {len(cm)}")
    print(f"pokee-sourced: {stat['pokee']}  derived: {stat['derived']}  blank: {stat['blank']}")
    print(f"wrote {OUT_DIR / big_name} ({len(big_out)}B)")
    print(f"wrote {OUT_DIR / small_name} ({len(small_out)}B)")


if __name__ == "__main__":
    sys.exit(main())
