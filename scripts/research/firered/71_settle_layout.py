#!/usr/bin/env python3
"""调研(71) 用 bot.lua 同款读法重测，并对齐「哪个才是 DISPCNT」。

═══════════════════════════════════════════════════════════════════════════
【目前的混乱】
═══════════════════════════════════════════════════════════════════════════
同一个 io dump（0x04000000 起 16 字节）：
    40 31 00 00 29 96 A0 00 00 1E 00 00 00 00 0F 1C

按 GBA 标准布局解：
    0x04000000 DISPCNT  = 0x3140   BG 全关 ← 与画面矛盾
    0x04000002 DISPSTAT = 0x0000
    0x04000004 VCOUNT   = 0x9629   ← 不可能 >
    0x04000006 BG0CNT   = 0x00A0
    0x04000008 BG1CNT   = 0x1E00   ← bot.lua 注释说 BG0CNT 在 0x04000008

⚠ bot.lua 第 417/997 行：`emu:read16(0x04000008 + b * 2)` 读 BG{b}CNT
  ⇒ bot 认为 **BG0CNT = 0x04000008**
  而 GBA 硬件手册：**BG0CNT = 0x04000008**（正确！）
  我上面那份对照表把 BG0CNT 排在 0x06 是**我自己的表格错**。

GBA 真实偏移（硬件手册）：
    0x04000000 DISPCNT
    0x04000002 DISPSTAT
    0x04000004 VCOUNT
    0x04000006 BG0CNT   ← 这里！0x04000006 是 BG0CNT
    0x04000008 BG1CNT
    0x0400000A BG2CNT
    0x0400000C BG3CNT
    0x0400000E BG0HOFS

等等，两种说法冲突（0x06 vs 0x08）。

**唯一正确做法：用数据自证。**
   若 BG0CNT 在 0x06：BG0CNT=0x00A0 → charBase=0, screenBase=0, 8bpp
   若 BG0CNT 在 0x08：BG0CNT=0x1E00 → charBase=0, screenBase=0xF000, 4bpp

用 (69) 的穷举渲染测试哪个组合能还原截图 —— 这是唯一判据。

用法：python scripts/research/firered/71_settle_layout.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "renderprove"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render_bg(vram: bytes, char_base: int, screen_base: int,
              bpp8: bool) -> np.ndarray:
    out = np.zeros((160, 240), dtype=np.uint8)
    tb = 64 if bpp8 else 32
    for py in range(160):
        row = py // 8
        for px in range(240):
            col = px // 8
            eo = screen_base + (row * 32 + col) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            hf, vf = (ent >> 10) & 1, (ent >> 11) & 1
            pidx = (ent >> 12) & 0xF
            ly, lx = py % 8, px % 8
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


def main() -> int:
    from PIL import Image
    vram = (OUT / "A.vram.bin").read_bytes()
    pal = (OUT / "A.pal.bin").read_bytes()
    io = (OUT / "A.io.bin").read_bytes()
    target = np.asarray(Image.open(OUT / "shotA.png").convert("RGB"),
                        dtype=np.uint8)

    print("=" * 78)
    print("① IO dump 全部 u16")
    print("=" * 78)
    for o in range(0, min(len(io), 32), 2):
        print(f"  +0x{o:02X}: 0x{rd16(io, o):04X}")

    print("\n" + "=" * 78)
    print("② 按「disp 层」穷举：每层用 4 种 charBase × 32 种 screenBase")
    print("=" * 78)
    print("  对每层分别穷举，看单层能否还原整幅截图")

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
                rate = same / (240 * 160)
                results.append((rate, cb, sb, bpp8))

    results.sort(reverse=True)
    print(f"\n  前 15 个组合：")
    print(f"  {'相似度':>8} {'charBase':>10} {'screenBase':>12} {'色深':>6}")
    for rate, cb, sb, bpp8 in results[:15]:
        print(f"  {rate:>7.1%} 0x{cb:04X}    0x{sb:04X}       "
              f"{'8bpp' if bpp8 else '4bpp'}")

    print("\n" + "=" * 78)
    print("③ 判读")
    print("=" * 78)
    best = results[0] if results else (0, 0, 0, False)
    if best[0] > 0.3:
        print(f"  最佳组合能还原 {best[0]:.1%} ⇒ VRAM 与截图**同帧有效**")
        print(f"  该组合 charBase=0x{best[1]:04X} screenBase=0x{best[2]:04X} "
              f"{'8bpp' if best[3] else '4bpp'}")
    else:
        print(f"  最佳只还原 {best[0]:.1%} ⇒ **VRAM 与截图不匹配**")
        print(f"  可能原因：")
        print(f"    · 截图不是当帧（mGBA screenshot 有延迟）")
        print(f"    · 画面走 OBJ（sprite），不在 BG tilemap 里")
        print(f"    · 用了特殊模式（mode 2 上下屏分裂 / mode 4/5 位图模式）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
