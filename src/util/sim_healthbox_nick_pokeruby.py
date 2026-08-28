#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sim_healthbox_nick_pokeruby.py

文档：docs/HEALTHBOX_NICK_GDB_SIM.md

按 pokeruby `battle_interface.c` `sub_80451A0` / UpdateNickInHealthbox 逐步仿真：

  1) RenderTextHandleBold → 列缓冲（用 gdb AfterRender raw64）
  2) 日文 chrome：每非控制字符 CpuCopy32(elem 0x2B/2C/2D, col, N)
  3) pad：for i..6 再 CpuCopy32(0x2B, col, N)
  4) OBJ：每列上下各拷 32B（本脚本只可视化缓冲）

元件表（日版 AXVJ）：GetHealthboxElementGfxPtr
  base 0x0868EBE0，index*32（反汇编 lsl#24/lsr#19）

实测 0x2B 空白条 8×8 上半 tile：
  row0..1 = 全 0（OBJ 透明 → 镂空见战场）
  row2..4 = 装饰条
  row5..7 = 底色 2

用法：
  set PYTHONPATH=%cd%\\src
  python src\\util\\sim_healthbox_nick_pokeruby.py
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as e:  # pragma: no cover
    raise SystemExit("需要 Pillow：pip install Pillow") from e

REPO = Path(__file__).resolve().parents[2]
ROM = REPO / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
DEFAULT_LOG = REPO / "src" / "util" / "work" / "POKEMON_RUBY_AXVJ00" / "gdb_patcher_log.log"
OUT_DIR = REPO / "src" / "util" / "work" / "POKEMON_RUBY_AXVJ00" / "healthbox_nick_sim"

ELEM_TABLE = 0x68EBE0  # file offset (= VA 0x0868EBE0 - 0x08000000)
COLS = 7
COL_BYTES = 0x40
SCALE = 6

PAL = {
    0: (30, 90, 50),      # 透明 → 战场绿（仿真）
    1: (250, 250, 255),
    2: (220, 210, 180),  # 昵称底
    3: (180, 120, 60),
    6: (100, 200, 200),
    7: (80, 180, 180),
}


def _pal(n: int) -> tuple[int, int, int]:
    return PAL.get(n, (200, 200, 210))


def load_elem(rom: bytes, elem_id: int) -> bytes:
    off = ELEM_TABLE + elem_id * 32
    return bytes(rom[off : off + 32])


def cpu_copy32(src: bytes, dst: bytearray, dst_off: int, nbytes: int) -> None:
    """pokeruby CpuCopy32 — 按字节数拷（日版池 24 或 32）。"""
    dst[dst_off : dst_off + nbytes] = src[:nbytes]


def col_has_glyph_ink(col: bytes, bg: int = 2) -> bool:
    """下半 tile（row8..15 = bytes 32..63）是否有非底/非透明墨水。"""
    for b in col[32:64]:
        hi, lo = b >> 4, b & 0xF
        for n in (hi, lo):
            if n not in (0, bg):
                return True
    return False


def apply_pokeruby_chrome(
    cols: list[bytearray],
    elem_rom: dict[int, bytes],
    chrome_ids: list[int],
    copy_bytes: int,
    do_pad: bool,
) -> None:
    """chrome_ids：按源串非控制字符顺序的元件 id（来自 GDB NickChromeElem）。"""
    i = 0
    for eid in chrome_ids:
        if i >= COLS:
            break
        cpu_copy32(elem_rom[eid], cols[i], 0, copy_bytes)
        i += 1
    if do_pad:
        while i < COLS:
            cpu_copy32(elem_rom[0x2B], cols[i], 0, copy_bytes)
            i += 1


def seal_pad_transparent(cols: list[bytearray], bg_nibble: int = 2) -> None:
    """只封「无汉字墨水」列：把 nibble 0 改成底色，保留装饰条。"""
    bg_byte = (bg_nibble << 4) | bg_nibble
    for col in cols:
        if col_has_glyph_ink(bytes(col)):
            continue
        for i, b in enumerate(col):
            hi, lo = b >> 4, b & 0xF
            if hi == 0:
                hi = bg_nibble
            if lo == 0:
                lo = bg_nibble
            col[i] = (hi << 4) | lo


def parse_after_render_cols(log_text: str) -> tuple[int, list[bytes], list[int]]:
    """取最后一次 AfterRender 的 7×raw64，以及紧随的 ChromeElem id 序列。"""
    blocks = list(
        re.finditer(
            r"\[HealthboxNickAfterRender\].*?buf=0x([0-9A-Fa-f]+).*?(?=\[HealthboxNick|\Z)",
            log_text,
            re.S,
        )
    )
    if not blocks:
        raise SystemExit("日志无 HealthboxNickAfterRender")
    m = blocks[-1]
    buf = int(m.group(1), 16)
    blob = m.group(0)
    cols: list[bytes] = []
    for i in range(COLS):
        rm = re.search(rf"col{i}_raw64:\s*([0-9A-Fa-f]+)", blob)
        if not rm:
            raise SystemExit(f"AfterRender 缺 col{i}_raw64，请用新埋点重抓")
        cols.append(bytes.fromhex(rm.group(1))[:64].ljust(64, b"\x00"))

    # chrome ids：AfterRender 之后、下次 AfterRender/ObjCopy 之前
    rest = log_text[m.end() :]
    ids = [int(x, 16) for x in re.findall(r"\[NickChromeElem\] id=0x([0-9A-Fa-f]+)", rest)]
    # 截到 ObjCopy 或非 2B/2C/2D
    chrome_ids: list[int] = []
    for eid in ids:
        if eid in (0x2B, 0x2C, 0x2D):
            chrome_ids.append(eid)
        elif chrome_ids:
            break
        if len(chrome_ids) >= COLS:
            break
    return buf, cols, chrome_ids


def render_grid(variants: list[tuple[str, list[bytes]]], path: Path) -> None:
    cell_w, cell_h = 8 * SCALE + 4, 16 * SCALE + 4
    rows = len(variants)
    img = Image.new("RGB", (8 + COLS * cell_w, 24 + rows * (cell_h + 18)), (20, 20, 24))
    dr = ImageDraw.Draw(img)
    for vi, (title, cols) in enumerate(variants):
        y0 = 20 + vi * (cell_h + 18)
        dr.text((8, y0 - 14), title, fill=(240, 240, 240))
        for ci, col in enumerate(cols):
            x0 = 8 + ci * cell_w
            for y in range(16):
                for x in range(8):
                    if y < 8:
                        b = col[y * 4 + x // 2]
                    else:
                        b = col[32 + (y - 8) * 4 + x // 2]
                    n = (b & 0xF) if (x & 1) else (b >> 4)
                    color = _pal(n)
                    dr.rectangle(
                        [
                            x0 + x * SCALE,
                            y0 + y * SCALE,
                            x0 + (x + 1) * SCALE - 1,
                            y0 + (y + 1) * SCALE - 1,
                        ],
                        fill=color,
                    )
            # 标 chrome 24B 带
            dr.rectangle(
                [x0, y0, x0 + 8 * SCALE - 1, y0 + 6 * SCALE - 1],
                outline=(255, 80, 80),
            )
    img.save(path)


def count_transparent(cols: list[bytes]) -> int:
    n = 0
    for col in cols:
        for b in col:
            n += (b >> 4 == 0) + (b & 0xF == 0)
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--rom", type=Path, default=ROM)
    args = ap.parse_args()
    rom = args.rom.read_bytes()
    elems = {eid: load_elem(rom, eid) for eid in (0x2B, 0x2C, 0x2D)}
    print("elem 0x2B rows0-1 (should be transparent 00):", elems[0x2B][:8].hex())

    log_text = args.log.read_text(encoding="utf-8", errors="replace")
    buf, after_cols, chrome_ids = parse_after_render_cols(log_text)
    print(f"buf=0x{buf:08X} chrome_ids={[hex(x) for x in chrome_ids]}")

    def clone() -> list[bytearray]:
        return [bytearray(c) for c in after_cols]

    # A: 仅 Render（AfterRender）
    a = [bytes(c) for c in after_cols]

    # B: pokeruby 原版 chrome+pad 全 32B
    b = clone()
    apply_pokeruby_chrome(b, elems, chrome_ids, 32, do_pad=True)

    # C: P03 — chrome/pad 皆 24B（现网）
    c = clone()
    apply_pokeruby_chrome(c, elems, chrome_ids, 24, do_pad=True)

    # D: P03 + 只封无字列透明（逻辑正确；先前 veneer 寄存器搞砸）
    d = clone()
    apply_pokeruby_chrome(d, elems, chrome_ids, 24, do_pad=True)
    seal_pad_transparent(d)

    # E: chrome 24B、pad 用「实心底」代替 0x2B（pad 列不写透明顶）
    e = clone()
    solid = bytes([0x22] * 32)
    i = 0
    for eid in chrome_ids:
        if i >= COLS:
            break
        cpu_copy32(elems[eid], e[i], 0, 24)
        i += 1
    while i < COLS:
        cpu_copy32(solid, e[i], 0, 32)  # 实心盖满上半
        e[i][32:64] = b"\x22" * 32
        i += 1

    # F: P03e — 改字库 0x2B/2C/2D 顶两行为底色（无 veneer）
    elems_sealed = {
        eid: (bytes([0x22] * 8) + elems[eid][8:]) for eid in elems
    }
    f = clone()
    apply_pokeruby_chrome(f, elems_sealed, chrome_ids, 24, do_pad=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"pokeruby_sim_0x{buf:08X}.png"
    render_grid(
        [
            (f"A Render only  transp={count_transparent(a)}", a),
            (f"B stock 32B  transp={count_transparent([bytes(x) for x in b])}", [bytes(x) for x in b]),
            (f"C P03 24B  transp={count_transparent([bytes(x) for x in c])}", [bytes(x) for x in c]),
            (f"D seal pad (veneer易炸，已弃)  transp={count_transparent([bytes(x) for x in d])}", [bytes(x) for x in d]),
            (f"E solid pad  transp={count_transparent([bytes(x) for x in e])}", [bytes(x) for x in e]),
            (f"F P03e patch 2B/2C/2D top  transp={count_transparent([bytes(x) for x in f])}", [bytes(x) for x in f]),
        ],
        out,
    )
    print("wrote", out)
    print("注：本图只画昵称 7 列缓冲，不是完整血条 OAM；绿=透明。现网采用 F（字库顶行），禁 D veneer。")


if __name__ == "__main__":
    main()
