#!/usr/bin/env python3
"""调研(201) 取出字形页表，导出整张字库 —— 算法已完全还原。

═══════════════════════════════════════════════════════════════════════════
【(200) 已完全还原的取字形算法】
═══════════════════════════════════════════════════════════════════════════
函数 0x081DB3EE（入口），入参 r0 = 字形码（16 位：hi<<8 | lo）：

  ; 阶段 1：按 hi 页取该页基址
  0x081DB3F4  lsrs r7, r7, #8        r7 = hi
  0x081DB3F6  cmp  r7, #0xA          hi <= 10 走页表
  0x081DB3FA  lsls r7, r7, #2        hi*4
  0x081DB3FC  ldr  r5, [pc,#0xA4]    r5 = 页表基址 PAGES
  0x081DB3FE  ldr  r5, [r5, r7]      r5 = PAGES[hi]         ← 页基址
  0x081DB408  ldr  r5, [pc,#0x9C]    （hi>10 时用默认页）

  ; 阶段 2：按 lo 算页内偏移
  0x081DB412  ands r4, r7(=0xFF)     r4 = lo
  0x081DB414  lsrs r7, r4, #3        lo >> 3      = 组号 g
  0x081DB416  lsls r7, r7, #9        g * 512
  0x081DB41A  ands r4, #7            lo & 7       = 组内号 k
  0x081DB41C  lsls r4, r4, #5        k * 32
  0x081DB41E  adds r4, r4, r7        offset = g*512 + k*32
  0x081DB420  adds r4, r4, r5        r4 = 页基址 + offset   ★字形地址

  ; 阶段 3：连搬 4 个 32B 块到 4 个 VRAM 位置
  0x081DB422  ldr  r6,[pc,#0x88]     r6 = 目标基址
  0x081DB428  bl   0x081DB49C        r0=r4+0x00, r1=r6+0x00
  0x081DB434  bl   0x081DB49C        r0=r4+0x10, r1=r6+0x20
  0x081DB440  bl   0x081DB49C        r0=r4+0x40, r1=r6+0x40
  0x081DB44C  bl   0x081DB49C        r0=r4+0x60, r1=r6+0x60
  0x081DB450  bl   0x081DB630        算字宽 → strb 到 r1, 再写 0x0D

【关键数字】
  每页 256 个码位 (lo = 0..255)
  每 8 个字为一组，占 512 字节  ⇒ 每组 8 字 × 64 字节
  ⇒ **每个字形 64 字节** = 8x8 4bpp × 2（上下两半）
  组内第 k 个字的地址 = 组基址 + k*32

  4 次搬运用的是 +0x00 / +0x10 / +0x40 / +0x60：
    +0x00 和 +0x10 相差 16，+0x40 和 +0x60 相差 32 —— 
    说明实际布局比「每字 64 连续」更复杂，需要看 0x081DB49C 做什么。

【本脚本】
 ① 解析 0x081DB3EE 附近所有 PC 字面量，拿到 PAGES 表地址、默认页、目标基址
 ② dump PAGES 表（11 项 u32）→ 得到 11 个页基址
 ③ 反汇编 0x081DB49C（真正的搬运函数），确认搬运单位和目标
 ④ 按公式从每个页基址导出 256 个码位的 64 字节字形
 ⑤ 渲染成整张字库 PNG（11 页 × 256 字）
 ⑥ 用导出的字形去 ROM 验证（应能在页基址处直接找到原字节）

用法：python scripts/research/firered/201_dump_font_table.py
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import numpy as np
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "font201"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000

FN = 0x081DB3EE
COPY_FN = 0x081DB49C


def save_png(path: Path, arr: np.ndarray) -> None:
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack(">I", len(data)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9))
                     + chunk(b"IEND", b""))


def decode_pc_lits(rom: bytes, lo: int, hi: int) -> list[dict]:
    """手工解 Thumb LDR/ADR 的 PC 相对字面量。"""
    out = []
    addr = lo
    i = lo - BASE
    end = hi - BASE
    while i < end:
        hw = rom[i] | (rom[i + 1] << 8)
        if (hw & 0xF800) == 0x4800:
            rd = (hw >> 8) & 7
            tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
            out.append({"pc": addr, "kind": "ldr", "rd": rd, "lit": tgt})
        elif (hw & 0xF800) == 0xA000:
            rd = (hw >> 8) & 7
            tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
            out.append({"pc": addr, "kind": "adr", "rd": rd, "lit": tgt})
        i += 2
        addr += 2
    return out


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()

    # ── ① 解出函数里的 PC 字面量 ─────────────────────
    print("=" * 78)
    print(f"① 0x{FN:08X} 函数内的 PC 字面量")
    print("=" * 78)
    lits = decode_pc_lits(zh, FN, FN + 0x80)
    seen = set()
    for L in lits:
        if L["lit"] in seen:
            continue
        seen.add(L["lit"])
        o = L["lit"] - BASE
        if not (0 <= o < len(zh) - 4):
            continue
        val = struct.unpack_from("<I", zh, o)[0]
        oval = struct.unpack_from("<I", ja, o)[0]
        print(f"  0x{L['pc']:08X}  {L['kind']:<4} r{L['rd']}  "
              f"lit@0x{L['lit']:08X} = 0x{val:08X}  原版=0x{oval:08X}")

    # ── ② 反汇编搬运函数 0x081DB49C ──────────────────
    print("\n" + "=" * 78)
    print(f"② 搬运函数 0x{COPY_FN:08X}")
    print("=" * 78)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    for ins in md.disasm(zh[COPY_FN - BASE:COPY_FN - BASE + 0xC0], COPY_FN):
        raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
        print(f"  0x{ins.address:08X}  {raw.hex():<8} "
              f"{ins.mnemonic:<8} {ins.op_str}")

    # ── ③ 找页表：0x081DB3FC 和 0x081DB408 的字面量 ──
    print("\n" + "=" * 78)
    print("③ 关键指针")
    print("=" * 78)
    key = {}
    for L in lits:
        o = L["lit"] - BASE
        if not (0 <= o < len(zh) - 4):
            continue
        val = struct.unpack_from("<I", zh, o)[0]
        if L["pc"] == 0x081DB3FC:
            key["pages_tbl"] = val
        elif L["pc"] == 0x081DB408:
            key["default_page"] = val
        elif L["pc"] == 0x081DB422:
            key["target_base"] = val
        elif L["pc"] == 0x081DB438:
            key["off3"] = val
        elif L["pc"] == 0x081DB444:
            key["off4"] = val
    for k, v in key.items():
        print(f"  {k:<14} = 0x{v:08X}")

    pages_tbl = key.get("pages_tbl")
    if not pages_tbl:
        print("  ✘ 没找到页表地址")
        return 1

    # ── ④ dump 页表（先看 16 项）─────────────────────
    print("\n" + "=" * 78)
    print(f"④ 页表 @0x{pages_tbl:08X}")
    print("=" * 78)
    o = pages_tbl - BASE
    pages = []
    for k in range(16):
        if o + k * 4 + 4 > len(zh):
            break
        v, ov = struct.unpack_from("<II", zh, o + k * 4)
        pages.append(v)
        print(f"  [{k:>2}] 0x{v:08X}   原版=0x{ov:08X}")

    # ── ⑤ 按公式导出字形 ────────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 按公式导出：offset = (lo>>3)*512 + (lo&7)*32，字长 64B")
    print("=" * 78)
    glyphs = []
    for hi_i, page in enumerate(pages[:11]):
        if not (BASE <= page < BASE + len(zh)):
            continue
        counts = {"ink": 0, "blank": 0}
        for lo in range(256):
            off = ((lo >> 3) << 9) + ((lo & 7) << 5)
            a = page + off - BASE
            if a < 0 or a + 64 > len(zh):
                break
            body = zh[a:a + 64]
            m = np.vstack([tile_nibs(body[:32]), tile_nibs(body[32:64])])
            ink = int(np.isin(m, [11, 12]).sum())
            if ink > 3:
                counts["ink"] += 1
            else:
                counts["blank"] += 1
            glyphs.append({"hi": hi_i, "lo": lo, "addr": page + off,
                           "mat": m, "ink": ink})
        print(f"  page[{hi_i}] 0x{page:08X}: 有墨 {counts['ink']} / 空 {counts['blank']}")

    print(f"\n  总导出 {len(glyphs)} 个码位，其中有墨 "
          f"{sum(1 for g in glyphs if g['ink'] > 3)} 个")

    # ── ⑥ 渲染整张字库 ──────────────────────────────
    print("\n" + "=" * 78)
    print("⑥ 渲染整张字库 PNG")
    print("=" * 78)
    valid = [g for g in glyphs if g["ink"] > 3]
    if not valid:
        print("  ✘ 没有有墨字形")
        return 1

    SCALE = 2
    cols = 32
    rows = (len(glyphs) + cols - 1) // cols
    cw, chh = 8 * SCALE + 2, 16 * SCALE + 2
    colors = {0: (40, 40, 40), 10: (10, 10, 10),
              11: (160, 160, 160), 12: (250, 250, 250)}
    img = np.full((rows * chh, cols * cw, 3), 13, dtype=np.uint8)
    for i, g in enumerate(glyphs):
        ry, rx = divmod(i, cols)
        y0 = ry * chh + 1
        x0 = rx * cw + 1
        for y in range(16):
            for x in range(8):
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = \
                    colors.get(int(g["mat"][y, x]), (255, 0, 0))
    p = OUT / "FONT_ALL.png"
    save_png(p, img)
    print(f"  ✔ {p}  ({img.shape[1]}x{img.shape[0]}, "
          f"{len(glyphs)} 码位 / {len(valid)} 有墨)")

    # 只画有墨的
    rows2 = (len(valid) + cols - 1) // cols
    img2 = np.full((rows2 * chh, cols * cw, 3), 13, dtype=np.uint8)
    for i, g in enumerate(valid):
        ry, rx = divmod(i, cols)
        y0 = ry * chh + 1
        x0 = rx * cw + 1
        for y in range(16):
            for x in range(8):
                img2[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                     x0 + x * SCALE:x0 + (x + 1) * SCALE] = \
                    colors.get(int(g["mat"][y, x]), (255, 0, 0))
    p2 = OUT / "FONT_INKED.png"
    save_png(p2, img2)
    print(f"  ✔ {p2}  ({img2.shape[1]}x{img2.shape[0]}, {len(valid)} 字)")

    # ── ⑦ 验证：导出的字形与 VRAM 里的对照 ─────────
    print("\n" + "=" * 78)
    print("⑦ 验证：页表内容在原版里是什么")
    print("=" * 78)
    for hi_i, page in enumerate(pages[:11]):
        if not (BASE <= page < BASE + len(zh)):
            continue
        o2 = page - BASE
        nf = sum(1 for b in ja[o2:o2 + 512] if b == 0xFF)
        print(f"  page[{hi_i}] 0x{page:08X}  原版该区 512B 中 FF={nf}/512")

    meta = [{"hi": g["hi"], "lo": g["lo"], "addr": g["addr"], "ink": g["ink"]}
            for g in glyphs]
    (OUT / "font.json").write_text(
        json.dumps({"pages": pages[:11], "key": key, "glyphs": meta},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'font.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
