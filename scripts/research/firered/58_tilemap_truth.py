#!/usr/bin/env python3
"""调研(58) 从 tilemap 反查：屏幕上那串中文，到底用了哪些 tile。

═══════════════════════════════════════════════════════════════════════════
【(57) 的教训】
═══════════════════════════════════════════════════════════════════════════
(57) 把 VRAM 整体按 4bpp 切成 3072 个 tile 来找「像汉字的」，
但那是**盲扫**：VRAM 里绝大部分是没在用的垃圾，找到的「像字」多半是图标。

而且 BG0CNT=0x1E00 → charBase=0、screenBase=0xF000，
BG3CNT=0x1C0F → charBase=0xC000、screenBase=0xE000。
**必须按每层真正用的 charBase/screenBase 去读**，不能全局扫。

═══════════════════════════════════════════════════════════════════════════
【正确做法：从 tilemap 反推】
═══════════════════════════════════════════════════════════════════════════
① 读 BG0 的 tilemap（screenBase=0xF000，30×20 表项，每项 u16）
② 表项格式：bit0-9 = tile 序号，bit10 = 水平翻转，bit11 = 垂直翻转，
             bit12-15 = 调色板
③ 取屏幕上**有文字的那几行**的 tile 序号
④ 用这些序号 × 32 字节去 charBase 区取真字形，画出来看

这样看到的才是**屏幕上真实显示的** tile，不会再被盲扫误导。

同时回答：E> 中文文本用什么编码进 tilemap 的？
   若 8×8 tile 直接是完整汉字 ⇒ 8px 汉字（不可能，放不下）
   若一个汉字占 2×2 tile ⇒ 12×12 或 16×16 字模
   若一个汉字占 1 tile + 偏移 ⇒ 8+4 拼接

用法：python scripts/research/firered/58_tilemap_truth.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram3"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def draw_tile4bpp(vram: bytes, tile_idx: int, char_base: int = 0) -> list[str]:
    """从 VRAM 取 4bpp 8×8 tile 并画出来。tile_idx 是相对 charBase 的序号。"""
    off = char_base + tile_idx * 32
    if off + 32 > len(vram):
        return ["<越界>"] * 8
    blob = vram[off:off + 32]
    out = []
    for row in range(8):
        rb = blob[row * 4:(row + 1) * 4]
        line = ""
        for col in range(8):
            byte = rb[col // 2]
            pix = (byte & 0x0F) if col % 2 == 0 else (byte >> 4)
            line += ("#" if pix else ".")
        out.append(line)
    return out


def main() -> int:
    tag = "s1"
    vram = (OUT / f"{tag}.vram.bin").read_bytes()
    io = (OUT / f"{tag}.ioblk.bin").read_bytes()
    pal = (OUT / f"{tag}.pal.bin").read_bytes()

    print("=" * 78)
    print(f"① {tag} 的层配置")
    print("=" * 78)
    dispcnt = rd16(io, 0)
    print(f"  DISPCNT = 0x{dispcnt:04X}  "
          f"BG0={dispcnt&1} BG1={(dispcnt>>1)&1} BG2={(dispcnt>>2)&1} "
          f"BG3={(dispcnt>>3)&1} OBJ={(dispcnt>>4)&1}")
    layers = []
    for b in range(4):
        v = rd16(io, 8 + b * 2)
        cb = ((v >> 2) & 3) * 0x4000
        sb = ((v >> 8) & 0x1F) * 0x800
        bpp8 = (v >> 7) & 1
        size = v >> 14
        enabled = (dispcnt >> b) & 1
        layers.append((b, v, cb, sb, bpp8, size, enabled))
        print(f"  BG{b}CNT=0x{v:04X} charBase=0x{cb:04X} screenBase=0x{sb:04X} "
              f"{'8bpp' if bpp8 else '4bpp'} size={size} "
              f"{'启用' if enabled else '关闭'}")

    # ── ② 逐层读 tilemap，找「有大量非零 tile」的行 ─────────────────
    print("\n" + "=" * 78)
    print("② 各层 tilemap：哪些行有内容（文字行会集中出现非零 tile）")
    print("=" * 78)
    for b, v, cb, sb, bpp8, size, en in layers:
        if not en:
            continue
        # size=0 → 32×32 表项（256×256 像素），但屏显 30×20
        base = sb
        if base + 0x800 > len(vram):
            print(f"  BG{b}: screenBase 0x{base:04X} 超出 VRAM，跳过")
            continue
        tm = vram[base:base + 0x800]
        print(f"\n  ---- BG{b}（charBase=0x{cb:04X} screenBase=0x{sb:04X}）----")
        rows_used = 0
        for row in range(20):
            ents = [rd16(tm, (row * 32 + col) * 2) for col in range(30)]
            nz = sum(1 for e in ents if (e & 0x3FF) != 0)
            if nz > 3:
                rows_used += 1
                if rows_used <= 6:
                    print(f"    行 {row:>2}: {nz:>2} 个非零 tile  "
                          f"前 10 个序号 {[e & 0x3FF for e in ents[:10]]}")
        print(f"    ⇒ 有内容的行：{rows_used}")

    # ── ③ 对「有内容的行」画 tile ─────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 把有内容的行画出来（用该层的 charBase）")
    print("=" * 78)
    for b, v, cb, sb, bpp8, size, en in layers:
        if not en or bpp8:
            continue              # 先只看 4bpp
        base = sb
        if base + 0x800 > len(vram):
            continue
        tm = vram[base:base + 0x800]
        print(f"\n  ===== BG{b} =====")
        printed = 0
        for row in range(20):
            ents = [rd16(tm, (row * 32 + col) * 2) for col in range(30)]
            nz = sum(1 for e in ents if (e & 0x3FF) != 0)
            if nz <= 3:
                continue
            print(f"\n    行 {row}:")
            # 取前 16 个 tile 拼成一条图
            for lr in range(8):
                line = ""
                for col in range(16):
                    e = ents[col]
                    tidx = e & 0x3FF
                    flip = (e >> 10) & 1
                    art = draw_tile4bpp(vram, tidx, cb)
                    s = art[lr] if lr < len(art) else "?" * 8
                    if flip:
                        s = s[::-1]
                    line += s
                print(f"      |{line}|")
            printed += 1
            if printed >= 4:
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
