#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_pool_safety.py — 画布池安全区校验（全局号空间，判据：BG tilemap 是否引用）

术语
====
「全局号」(gnum) = 物理字节地址 / 32，范围 0..3071（VRAM 96KB）。
对某个 BG 图层：  gnum = char_base*512 + tile_index      （4bpp）
                  gnum = char_base*512 + tile_index, +1   （8bpp，1 tile = 64B）
物理地址 = gnum*32。

🔴 上一次分析把「tile_index」当成全局号，**没有按 charBase 归位** ⇒ 结论全错。
本脚本按层归位后重算。

用法：
    python scripts/verify_pool_safety.py
"""
import argparse
import glob
import os
import sys

DISPCNT = 0x00
BG_CNT = (0x08, 0x0A, 0x0C, 0x0E)
SIZES = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}


def u16(b, o):
    return b[o] | (b[o + 1] << 8)


def parse_bgcnt(v):
    return {
        "prio": v & 3,
        "char_base": (v >> 2) & 3,
        "mosaic": (v >> 6) & 1,
        "bpp": 8 if (v >> 7) & 1 else 4,
        "screen_base": (v >> 8) & 0x1F,
        "overflow": (v >> 13) & 1,
        "size_bits": (v >> 14) & 3,
    }


def refs_of_bg(vram, cfg):
    """返回该 BG 引用的『全局号』集合"""
    refs = set()
    cols, rows = SIZES[cfg["size_bits"]]
    cols //= 32
    rows //= 32
    cbnum = cfg["char_base"] * 512
    base = 0x800 * cfg["screen_base"]
    step = 2 if cfg["bpp"] == 8 else 1
    for r in range(rows):
        for c in range(cols):
            off = base + (r * 32 + c) * 0x800
            for i in range(0, 0x800, 2):
                if off + i + 1 >= len(vram):
                    break
                t = u16(vram, off + i) & 0x3FF
                g = cbnum + t
                refs.add(g)
                for k in range(1, step):
                    refs.add(g + k)
    return refs


def free_segments(mask, lo, hi):
    """在 [lo,hi) 内找 mask 中未置位的连续段"""
    out, n, start = [], 0, lo
    for i in range(lo, hi):
        if mask.get(i, False):
            if n:
                out.append((start, n))
            n = 0
            start = i + 1
        else:
            if n == 0:
                start = i
            n += 1
    if n:
        out.append((start, n))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=".tmp/ss*_vram.bin")
    args = ap.parse_args()

    vrams = sorted(glob.glob(args.glob))
    if not vrams:
        print("没有找到 dump：", args.glob)
        return 1

    union = {}
    per_layer_union = {}

    for vp in vrams:
        tag = os.path.basename(vp).replace("_vram.bin", "")
        iop = vp.replace("_vram.bin", "_io.bin")
        vram = open(vp, "rb").read()
        io = open(iop, "rb").read() if os.path.exists(iop) else b"\x00" * 0x60
        dispcnt = u16(io, DISPCNT)
        bg_en = [(dispcnt >> (8 + i)) & 1 for i in range(4)]

        print(f"\n--- {tag} --- DISPCNT=0x{dispcnt:04X} mode={dispcnt & 7} "
              f"BG_EN={bg_en} OBJ_EN={(dispcnt >> 12) & 1}")
        for i in range(4):
            v = u16(io, BG_CNT[i])
            cfg = parse_bgcnt(v)
            if not bg_en[i]:
                print(f"  BG{i} CNT=0x{v:04X}  (disabled)")
                continue
            r = refs_of_bg(vram, cfg)
            gn = [x for x in r]
            print(f"  BG{i} CNT=0x{v:04X} prio={cfg['prio']} charBase={cfg['char_base']} "
                  f"({cfg['char_base'] * 512} 号起) sb={cfg['screen_base']} "
                  f"sz={cfg['size_bits']} {cfg['bpp']}bpp → 全局号 {len(r)} 个 "
                  f"[{min(gn)},{max(gn)}]")
            for x in r:
                union[x] = True
                per_layer_union.setdefault(i, set()).add(x)

    print()
    print("=" * 78)
    print(f"全部图层并集：{len(union)} 全局号")
    print("=" * 78)
    for i in range(4):
        s = per_layer_union.get(i)
        if s:
            print(f"  BG{i}: {len(s)} 号 [{min(s)},{max(s)}]")
    objs = sorted(per_layer_union.get(4, []))
    print()

    # 每个 charBase 块（512 号）内的空闲段
    for cb in range(4):
        lo, hi = cb * 512, cb * 512 + 512
        segs = free_segments(union, lo, hi)
        used = sum(1 for i in range(lo, hi) if union.get(i))
        print(f"\ncharBase {cb}  全局号 [{lo},{hi})  桩: 0x06000000+{cb * 0x4000:05X}"
              f"  已引用 {used}/512  空闲 {512 - used}")
        for s, l in sorted(segs, key=lambda x: -x[1])[:6]:
            print(f"    [{s:5d},{s + l:5d})  {l:4d} 号")

    # 全局空闲段
    print()
    print("=" * 78)
    print("全 VRAM 空闲连续段（前 20 大）")
    print("=" * 78)
    for s, l in sorted(free_segments(union, 0, 3072), key=lambda x: -x[1])[:20]:
        print(f"  [{s:5d},{s + l:5d})  {l:4d} 号   "
              f"cb{ s // 512 }  桩 0x06000000+{s * 32:05X}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
