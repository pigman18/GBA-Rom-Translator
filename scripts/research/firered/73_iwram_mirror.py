#!/usr/bin/env python3
"""调研(73) 定案：mGBA 的 Lua 读 IO 区不可靠，改用 IWRAM 镜像。

═══════════════════════════════════════════════════════════════════════════
【铁证链】
═══════════════════════════════════════════════════════════════════════════
(72) 实测：
    [HEAD 0x03000000] 40 31 00 00 2B 96 00 00   ← IWRAM
    [HEAD 0x04000000] 40 31 00 00 29 96 A0 00   ← IO

    IWRAM 前 16 字节: 40 31 00 00 2b 96 00 00 00 1e 00 00 00 00 0f 1c
    IO    前 16 字节: 40 31 00 00 29 96 a0 00 00 1e 00 00 00 00 0f 1c
    **16 字节里 14 个相同**

⇒ IO 读出来的东西 ≈ IWRAM 开头的内容，不是真正的硬件寄存器。

这解释了所有怪现象：
  · VCOUNT = 0x9629（IWRAM 里的数据，不是扫描线）
  · BG0-3 全关（那是 IWRAM 里的某个变量，不是 DISPCNT）
  · BGxHOFS 全是 0x1C18（IWRAM 里连续的数据）
  · 穷举渲染全部失败（因为配置本来就是错的）

═══════════════════════════════════════════════════════════════════════════
【但 IWRAM 开头那个镜像本身就是有用的】
═══════════════════════════════════════════════════════════════════════════
IWRAM 前 16 字节：
    40 31 00 00 2b 96 00 00 00 1e 00 00 00 00 0f 1c
按 u16 读：
    0x3140, 0x0000, 0x962B, 0x0000, 0x1E00, 0x0000, 0x0000, 0x1C0F

这**恰好就是 GBA 寄存器排布**（DISPCNT, DISPSTAT, VCOUNT?, BG0CNT...），
只是 VCOUNT 那个位置存的是 0x962B（可能是游戏自己的计数器）。

⇒ **IWRAM 开头是一份 IO 寄存器快照/镜像**，游戏用它做双缓冲。
   要读 DISPCNT 等寄存器，应读**这份镜像**，而不是 IO 区。

═══════════════════════════════════════════════════════════════════════════
【本脚本验证】
═══════════════════════════════════════════════════════════════════════════
 ① 比较 IWRAM 镜像与 IO 读数，确认镜像更自洽
 ② 用镜像里的 BG0CNT=0x1E00 做渲染，看能否还原截图
 ③ 若能还原 ⇒ 找到了正确数据源

用法：python scripts/research/firered/73_iwram_mirror.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT3 = ROOT / "work" / "_probe" / "ewram3"
OUTP = ROOT / "work" / "_probe" / "renderprove"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render_bg(vram: bytes, char_base: int, screen_base: int,
              bpp8: bool, hoff: int = 0, voff: int = 0) -> np.ndarray:
    out = np.zeros((160, 240), dtype=np.uint8)
    tb = 64 if bpp8 else 32
    for py in range(160):
        row = (py + voff) // 8
        for px in range(240):
            col = (px + hoff) // 8
            if row >= 32 or col >= 32:
                continue
            eo = screen_base + (row * 32 + col) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            hf, vf = (ent >> 10) & 1, (ent >> 11) & 1
            pidx = (ent >> 12) & 0xF
            ly, lx = (py + voff) % 8, (px + hoff) % 8
            if vf:
                ly = 7 - ly
            if hf:
                lx = 7 - lx
            to = char_base + tidx * tb
            if bpp8:
                if to + ly * 8 + lx < len(vram):
                    out[py, px] = vram[to + ly * 8 + lx]
            else:
                by = to + ly * 4 + lx // 2
                if by < len(vram):
                    b = vram[by]
                    p = (b & 0x0F) if lx % 2 == 0 else (b >> 4)
                    if p:
                        out[py, px] = pidx * 16 + p
    return out


def to_rgb(pal: bytes, idx: np.ndarray) -> np.ndarray:
    cols = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        cols.append(((v & 0x1F) * 255 // 31,
                     ((v >> 5) & 0x1F) * 255 // 31,
                     ((v >> 10) & 0x1F) * 255 // 31))
    return np.array(cols, dtype=np.uint8)[idx]


def decode_bgcnt(v: int) -> dict:
    return {"charBase": ((v >> 2) & 3) * 0x4000,
            "screenBase": ((v >> 8) & 0x1F) * 0x800,
            "bpp8": bool((v >> 7) & 1),
            "size": v >> 14, "prio": v & 3}


def main() -> int:
    iwram = (OUT3 / "s1.iwram.bin").read_bytes()
    iodump = (OUT3 / "s1.ioblk.bin").read_bytes()
    vram = (OUT3 / "s1.vram.bin").read_bytes()
    pal = (OUT3 / "s1.pal.bin").read_bytes()

    print("=" * 78)
    print("① IWRAM 镜像 vs IO 读数")
    print("=" * 78)
    names = ["DISPCNT", "DISPSTAT", "VCOUNT", "BG0CNT", "BG1CNT",
             "BG2CNT", "BG3CNT", "BG0HOFS"]
    print(f"  {'寄存器':<10} {'IO 读数':>10} {'IWRAM 镜像':>12}  一致")
    for i, n in enumerate(names):
        a = rd16(iodump, i * 2)
        b = rd16(iwram, i * 2)
        print(f"  {n:<10} 0x{a:04X}     0x{b:04X}       "
              f"{'✓' if a == b else '✗'}")

    print("\n" + "=" * 78)
    print("② 用 IWRAM 镜像的寄存器值解码")
    print("=" * 78)
    for i in range(3, 7):
        v = rd16(iwram, i * 2)
        info = decode_bgcnt(v)
        print(f"  BG{i-3}CNT = 0x{v:04X}  char=0x{info['charBase']:04X} "
              f"scr=0x{info['screenBase']:04X} "
              f"{'8bpp' if info['bpp8'] else '4bpp'} prio={info['prio']}")

    # ── ③ 用镜像里的 BG0CNT 渲染，比对截图 ────────────────────────
    print("\n" + "=" * 78)
    print("③ 用镜像寄存器渲染，比对 s1.png")
    print("=" * 78)
    try:
        from PIL import Image
        target = np.asarray(Image.open(OUT3 / "s1.png").convert("RGB"),
                            dtype=np.uint8)
    except Exception as e:
        print(f"  读截图失败: {e}")
        return 0

    bg0 = rd16(iwram, 6)     # BG0CNT 在 +0x06
    info = decode_bgcnt(bg0)
    print(f"  用 BG0CNT=0x{bg0:04X}: char=0x{info['charBase']:04X} "
          f"scr=0x{info['screenBase']:04X} "
          f"{'8bpp' if info['bpp8'] else '4bpp'}")
    idx = render_bg(vram, info["charBase"], info["screenBase"], info["bpp8"])
    rgb = to_rgb(pal, idx)
    same = int((rgb == target).all(axis=2).sum())
    print(f"  还原度：{same/(240*160):.1%}")

    # 穷举配合镜像的其它层
    print(f"\n  再穷举 charBase × screenBase（用镜像里有值的 BG 层）：")
    results = []
    for bpp8 in (False, True):
        for cb in (0, 0x4000, 0x8000, 0xC000):
            for sb in range(0, 0x8000, 0x800):
                if sb + 0x800 > len(vram):
                    continue
                i2 = render_bg(vram, cb, sb, bpp8)
                if i2.max() == 0:
                    continue
                r2 = to_rgb(pal, i2)
                s2 = int((r2 == target).all(axis=2).sum())
                results.append((s2 / (240 * 160), cb, sb, bpp8))
    results.sort(reverse=True)
    for rate, cb, sb, bpp8 in results[:8]:
        print(f"    {rate:>7.1%}  char=0x{cb:04X} scr=0x{sb:04X} "
              f"{'8bpp' if bpp8 else '4bpp'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
