#!/usr/bin/env python3
"""调研(78) 穷举渲染（正确位定义），确认中文字形到底在哪。

═══════════════════════════════════════════════════════════════════════════
【寄存器读数（(77) 实测，正确地址）】
═══════════════════════════════════════════════════════════════════════════
  DISPCNT = 0x3140 → mode 0, BG=[1,0,0,0]（只 BG0）, OBJ=1
  BG0CNT = 0x00A0 → charBase=0x0000 screenBase=0x0000 **8bpp** prio=0
  BG1CNT = 0x1E00 → charBase=0x0000 screenBase=0xF000 4bpp
  BG2/BG3 = 0x0000

  注意 BG0 的 screenBase 与 charBase 都是 0，两者重叠 —— 这本身可疑。
  但 8bpp 时 tilemap 在 0x0000、tiles 也在 0x0000 会互相覆盖，
  所以真实配置大概率不是这个值，或者游戏用了别的机制。

【本脚本】
 对 g1..g4 每张图，穷举：
   · 4 个 charBase × 32 个 screenBase × 2 种色深
   · 允许 hoff/voff 取 0（先不做偏移）
 找还原度最高的组合。同时对 OBJ 做一次简单统计。

用法：python scripts/research/firered/78_bruteforce_correct.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render_bg(vram: bytes, cb: int, sb: int, bpp8: bool) -> np.ndarray:
    out = np.zeros((160, 240), dtype=np.uint8)
    tb = 64 if bpp8 else 32
    for py in range(160):
        row = py // 8
        for px in range(240):
            col = px // 8
            eo = sb + (row * 32 + col) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            hf, vf = (ent >> 10) & 1, (ent >> 11) & 1
            pil = (ent >> 12) & 0xF
            ly, lx = py % 8, px % 8
            if vf:
                ly = 7 - ly
            if hf:
                lx = 7 - lx
            to = cb + tidx * tb
            if bpp8:
                if to + ly * 8 + lx < len(vram):
                    out[py, px] = vram[to + ly * 8 + lx]
            else:
                by = to + ly * 4 + lx // 2
                if by < len(vram):
                    b = vram[by]
                    p = (b & 0x0F) if lx % 2 == 0 else (b >> 4)
                    if p:
                        out[py, px] = pil * 16 + p
    return out


def to_rgb(pal: bytes, idx: np.ndarray) -> np.ndarray:
    cols = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        cols.append(((v & 0x1F) * 255 // 31,
                     ((v >> 5) & 0x1F) * 255 // 31,
                     ((v >> 10) & 0x1F) * 255 // 31))
    return np.array(cols, dtype=np.uint8)[idx]


def main() -> int:
    from PIL import Image

    print("=" * 78)
    print("① 对 g1..g4 穷举渲染")
    print("=" * 78)
    for i in range(1, 5):
        png = OUT / f"g{i}.png"
        vp = OUT / f"g{i}.vram.bin"
        pp = OUT / f"g{i}.pal.bin"
        if not png.exists():
            continue
        target = np.asarray(Image.open(png).convert("RGB"), dtype=np.uint8)
        vram = vp.read_bytes()
        pal = pp.read_bytes()
        io = (OUT / f"g{i}.io.bin").read_bytes()
        dc = rd16(io, 0)

        # 指纹：看 4 张图是否不同
        import hashlib
        h = hashlib.md5(vram).hexdigest()[:10]

        results = []
        for bpp8 in (False, True):
            for cb in (0, 0x4000, 0x8000, 0xC000):
                for sb in range(0, 0x8000, 0x800):
                    if sb + 0x800 > len(vram):
                        continue
                    idx = render_bg(vram, cb, sb, bpp8)
                    if idx.max() == 0:
                        continue
                    rgb = to_rgb(pal, idx)
                    same = int((rgb == target).all(axis=2).sum())
                    results.append((same / (240 * 160), cb, sb, bpp8))
        results.sort(reverse=True)

        print(f"\n  g{i}: dc=0x{dc:04X} vram={h}")
        if results:
            for rate, cb, sb, bpp8 in results[:4]:
                print(f"      还原 {rate:>6.1%}  char=0x{cb:04X} "
                      f"scr=0x{sb:04X} {'8bpp' if bpp8 else '4bpp'}")
        else:
            print("      全部组合还原度为 0")

    # ── ② OAM 统计（OBJ 可能是文字载体）────────────────────────────
    print("\n" + "=" * 78)
    print("② OAM 统计（OBJ 是否在画字）")
    print("=" * 78)
    for i in range(1, 5):
        op = OUT / f"g{i}.oam.bin"
        if not op.exists():
            continue
        oam = op.read_bytes()
        act = []
        for k in range(len(oam) // 8):
            e = oam[k * 8:(k + 1) * 8]
            a0 = rd16(e, 0)
            a1 = rd16(e, 2)
            a2 = rd16(e, 4)
            if a0 & 0x0200:        # disabled
                continue
            if a0 == 0 and a1 == 0 and a2 == 0:
                continue
            act.append((k, a1 & 0x1FF, a0 & 0xFF, a2 & 0x3FF,
                        (a0 >> 13) & 3))
        print(f"  g{i}: 活跃 OBJ {len(act)}")
        for k, x, y, t, sz in act[:8]:
            print(f"      [{k:>3}] x={x:>3} y={y:>3} tile={t:>3} size={sz}")

    # ── ③ VRAM 里有没有「像汉字」的 2×2 tile 组 ────────────────────
    print("\n" + "=" * 78)
    print("③ VRAM 里「像汉字」的 tile（4bpp，有中等墨量且非纯填充）")
    print("=" * 78)
    vram = (OUT / "g1.vram.bin").read_bytes()
    from collections import Counter
    c = Counter()
    cand = []
    for k in range(len(vram) // 32):
        blob = vram[k * 32:(k + 1) * 32]
        s = set(blob)
        if s <= {0x00}:
            c["全00"] += 1
            continue
        if s <= {0x00, 0xFF}:
            c["仅00/FF"] += 1
            continue
        ink = sum(1 for b in blob for nib in (b & 0xF, b >> 4) if nib)
        if ink < 6:
            c["几乎空"] += 1
        elif ink > 56:
            c["几乎满"] += 1
        else:
            c["中等墨量"] += 1
            cand.append(k)
    print(f"  tile 分类：{dict(c)}")
    print(f"  中等墨量 tile：{len(cand)} 个")
    if cand:
        print(f"    前 30 个编号：{cand[:30]}")
        print(f"\n  抽样 8 个画出来：")
        for t in cand[:8]:
            blob = vram[t * 32:(t + 1) * 32]
            print(f"\n    tile {t}:")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for xx in range(8):
                    b = row[xx // 2]
                    p = (b & 0x0F) if xx % 2 == 0 else (b >> 4)
                    line += "." if p == 0 else "#"
                print(f"      {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
