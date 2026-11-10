#!/usr/bin/env python3
"""调研(172) 用干净字形（13×12，nibble 12 核心）反查 ROM。

═══════════════════════════════════════════════════════════════════════════
【现在手里有确定的字形】
═══════════════════════════════════════════════════════════════════════════
 26 个汉字，每个 13×12，来自 VRAM tilemap 的 pal=15 项。
 已肉眼确认内容：继续游戏 / 主角 / 时间 22:04 / 图鉴 62只 / 徽章 7枚 /
                开始新游戏

【反查思路】
 字形在 VRAM 里是 4bpp（nibble 10/11/12）。
 若 ROM 里有同样的数据（哪怕是 1/2/3），直接搜就能命中。

 但要注意：VRAM 里的值可能是**运行时映射**过的。
 所以除了原样搜，还要试：
   · nibble 12→2, 11→1, 10→0（归一化）
   · nibble 12→1, 其他→0（1bpp）
   · 只取字节的高/低半（4bpp 变 2bpp）

【本脚本】
 ① 从 VRAM 精确提取 26 个字（13×12）
 ② 转成几种可能存储形式
 ③ 每种都去 ROM 搜
 ④ 统计命中位置，找聚集区

用法：python scripts/research/firered/172_glyph_to_rom.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def pack_4bpp(cell: np.ndarray) -> bytes:
    """13 宽 → 每行按 8px tile 补到 16，4bpp 打包。"""
    h, w = cell.shape
    out = bytearray()
    for y in range(h):
        row = np.zeros(16, dtype=np.uint8)
        row[:min(w, 16)] = cell[y, :min(w, 16)]
        for x in range(0, 16, 2):
            out.append((row[x] << 4) | row[x + 1])
    return bytes(out)


def pack_1bpp(cell: np.ndarray) -> bytes:
    h, w = cell.shape
    out = bytearray()
    for y in range(h):
        for xx in range(0, min(w, 16), 8):
            b = 0
            for k in range(8):
                x = xx + k
                v = cell[y, x] if x < w else 0
                b = (b << 1) | (1 if v == 12 else 0)
            out.append(b)
    return bytes(out)


def pack_2bpp(cell: np.ndarray) -> bytes:
    h, w = cell.shape
    out = bytearray()
    for y in range(h):
        for xx in range(0, min(w, 16), 4):
            b = 0
            for k in range(4):
                x = xx + k
                v = cell[y, x] if x < w else 10
                q = 0 if v == 10 else (2 if v == 12 else 1)
                b = (b << 2) | q
            out.append(b)
    return bytes(out)


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    SB = 0xF000

    # 提取 26 个字
    def row_has_ink(r: int) -> bool:
        for c in range(30):
            e = rd16(vr, SB + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) != 15:
                continue
            off = (e & 0x3FF) * 32
            if off + 32 > len(vr):
                continue
            u = set(v for b in vr[off:off + 32] for v in (b & 0xF, b >> 4))
            if u & {11, 12}:
                return True
        return False

    text_rows = [r for r in range(20) if row_has_ink(r)]
    bands = []
    i = 0
    while i < len(text_rows):
        r = text_rows[i]
        r2 = (r + 1 if i + 1 < len(text_rows) and
              text_rows[i + 1] == r + 1 else None)
        bands.append((r, r2))
        i += 2 if r2 else 1

    PITCH, H = 13, 12
    glyphs = []
    for r, r2 in bands:
        rows = [r] + ([r2] if r2 else [])
        cv = np.full((len(rows) * 8, 240), 10, dtype=np.uint8)
        for yi, rr in enumerate(rows):
            for c in range(30):
                e = rd16(vr, SB + (rr * 32 + c) * 2)
                if ((e >> 12) & 0xF) != 15:
                    continue
                off = (e & 0x3FF) * 32
                if off + 32 > len(vr):
                    continue
                cv[yi * 8:(yi + 1) * 8, c * 8:(c + 1) * 8] = \
                    nibs(vr[off:off + 32])
        ink = (cv == 11) | (cv == 12)
        ys = np.flatnonzero(ink.any(axis=1))
        xs = np.flatnonzero(ink.any(axis=0))
        if not len(ys):
            continue
        y0, x0, x1 = int(ys[0]), int(xs[0]), int(xs[-1])
        core = cv[y0:y0 + H] if y0 + H <= cv.shape[0] else cv[y0:]
        if core.shape[0] < H:
            core = np.vstack([core,
                              np.full((H - core.shape[0], 240), 10,
                                      dtype=np.uint8)])
        x = x0
        while x + PITCH <= x1 + 4:
            cell = core[:, x:x + PITCH]
            if int(((cell == 11) | (cell == 12)).sum()) > 4:
                glyphs.append(cell)
            x += PITCH

    print(f"提取 {len(glyphs)} 个字（13×12）")

    # 三种打包
    forms = {
        "4bpp 原样": lambda c: pack_4bpp(c),
        "4bpp 归一(12→2,11→1,10→0)":
            lambda c: pack_4bpp(np.where(c == 12, 2,
                                         np.where(c == 11, 1, 0))
                                .astype(np.uint8)),
        "1bpp(12→1)": lambda c: pack_1bpp(c),
        "2bpp": lambda c: pack_2bpp(c),
    }

    for name, fn in forms.items():
        print("\n" + "=" * 78)
        print(f"① {name}")
        print("=" * 78)
        hits = []
        for gi, cell in enumerate(glyphs):
            pat = fn(cell)
            if len(set(pat)) <= 1:
                continue
            i = zh.find(pat)
            while i >= 0:
                hits.append((gi, i))
                i = zh.find(pat, i + 1)
        print(f"  命中 {len(hits)} 处"
              f"（{len({h[1] for h in hits})} 个不同位置）")
        if hits:
            z = Counter(h[1] // 0x10000 for h in hits)
            print(f"  按 64KB：")
            for k, v in z.most_common(8):
                print(f"    0x{BASE+k*0x10000:08X}: {v}")
            for gi, off in hits[:6]:
                print(f"    字{gi} → 0x{BASE+off:08X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
