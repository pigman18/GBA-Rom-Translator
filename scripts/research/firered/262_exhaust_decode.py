"""穷举所有小字解码组合，定死格式。

═══ 目标 ═══
拿 261 抓的 5 帧队伍界面快照里的 VRAM 小字 tile 作为**唯一真相**，
反查小字页表 0x08B74000 的数据，穷举以下维度，找出唯一能对上的组合：

  维度1 读序：noshift / swap / reverse
  维度2 输出尺寸：8x8(4B/行) / 8x16(2B/行)
  维度3 每字步长：64 / 32 / 16
  维度4 段偏移：0 / 0x10 / 0x100 等
  维度5 PAL 来源：party261 自己的 IWRAM
  维度6 IDX：0x081CDF40

一旦某组合能让 VRAM 里的真实小字 **精确重现**，就是正确格式。
"""
from __future__ import annotations

import itertools
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

P261 = ROOT / "work" / "_probe" / "party261"
IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]

PAGES_TABLES = {
    "small_0x08B74000": [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000,
                         0x08B70000, 0x08B80000, 0x08B90000, 0x08BA0000,
                         0x08BB0000, 0x08B64000, 0x08B68000],
    "main_0x089D08A0": [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C,
                        0x08B333A0, 0x08907C0C, 0x08AD690C, 0x08935A08,
                        0x08A72610, 0x08AB5404, 0x089B2B0C],
}


def load_frame(idx: int):
    tag = f"s{idx:02d}_party{idx:02d}"
    vr = (P261 / f"{tag}_vram.bin").read_bytes()
    iw = (P261 / f"{tag}_iwram.bin").read_bytes()
    return vr, iw


def mat(blob: bytes, w: int, h: int):
    m = np.zeros((h, w), dtype=np.uint8)
    per = w // 2
    for y in range(h):
        for x in range(w):
            off = y * per + x // 2
            if off >= len(blob):
                return None
            v = blob[off]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def decode(src: bytes, pal: bytes, order: str) -> bytes:
    out = bytearray()
    for r3 in range(16):
        if order == "noshift":
            v = src[r3] if r3 < len(src) else 0
        elif order == "swap":
            p = (r3 // 2) * 2
            v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        elif order == "reverse":
            v = src[15 - r3] if 15 - r3 < len(src) else 0
        else:
            v = 0
        i = IDX[v]
        off = i * 2
        out += pal[off:off + 2] if off + 1 < len(pal) else b"\x00\x00"
    return bytes(out)


# ── 从 261 的 VRAM 里取真实小字 tile ─────────────────────
vr, iw = load_frame(1)
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
print("=== party261 帧1 的 PAL 前 16 项 ===")
for k in range(16):
    print(f"  PAL[{k:2d}] = {PAL[k*2]:02x} {PAL[k*2+1]:02x}")

# 找 VRAM 里所有「6~8 高、有墨」的 tile 作为目标
targets = {}
for t in range(0, 1024):
    o = t * 32
    if o + 32 > len(vr):
        break
    m = mat(vr[o:o + 32], 8, 8)
    if m is None:
        continue
    txt = (m == 11) | (m == 12)
    ys = np.flatnonzero(txt.any(axis=1))
    xs = np.flatnonzero(txt.any(axis=0))
    ink = int(txt.sum())
    if 5 <= len(ys) <= 8 and 3 <= len(xs) <= 8 and 10 <= ink <= 50:
        targets[t] = vr[o:o + 32]
print(f"\n=== VRAM 里的小字候选 tile: {len(targets)} 个 ===")
print(f"  序号: {sorted(targets)[:20]}")

for t in sorted(targets)[:5]:
    m = mat(targets[t], 8, 8)
    print(f"\n  tile {t}:")
    for y in range(8):
        print("    " + "".join("#" if v == 12 else ("+" if v == 11 else ".")
                               for v in m[y]))

# ── 穷举 ─────────────────────────────────────────────────
print("\n" + "=" * 78)
print("穷举所有组合")
print("=" * 78)
results = []
STEPS = [64, 32, 16]
SEGS = [0x00, 0x10, 0x20, 0x30, 0x40, 0x100, 0x110]
ORDERS = ["noshift", "swap", "reverse"]

for tname, pages in PAGES_TABLES.items():
    for order, step, seg in itertools.product(ORDERS, STEPS, SEGS):
        hit_count = 0
        hit_detail = []
        for hi, pg in enumerate(pages):
            for lo in range(0, 256, 1):
                a = pg + lo * step + seg
                o = a - BASE
                if o < 0 or o + 16 > N:
                    continue
                d = decode(zh[o:o + 16], PAL, order)
                for t, tgt in targets.items():
                    if d == tgt:
                        hit_count += 1
                        hit_detail.append((t, hi * 256 + lo))
        if hit_count:
            results.append((hit_count, tname, order, step, seg, hit_detail[:6]))

results.sort(reverse=True)
if results:
    print(f"有命中的组合 {len(results)} 个，前 12：")
    for cnt, tn, od, st, sg, det in results[:12]:
        print(f"  命中 {cnt:>3}  页表={tn}  读序={od:<8} 步长={st:>2} "
              f"段偏移=0x{sg:03X}")
        print(f"      {[(t, hex(c)) for t, c in det]}")
else:
    print("  ✘ 所有组合 0 命中")
    print("\n  说明：VRAM 里的小字**不是**从这两张页表解出来的。")
    print("  检查：这些 tile 是否可能与主字库有关？")
    for t, tgt in list(targets.items())[:3]:
        p = zh.find(tgt)
        print(f"    tile {t}: ROM 直接搜 = "
              f"{'0x%08X' % (BASE + p) if p >= 0 else '-'}")
