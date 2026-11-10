"""小字用 2x2 拼 16x16（同大字），只是字宽 8 而非 12。

═══ 271 的决定性数据 ═══
   大字（207，成功）：背景占比 70.9%
   小字（我的 +0x00/+0x100 纵向）：背景占比 47.5%

  两张 PAL 等价（PAL261 只是把 PAL205 全部减 9），所以不是 PAL 问题。

⇒ 小字背景占比太低 = 字太多、留白太少
⇒ 说明小字也是 **16x16 网格**（和大字一样 2x2 拼），只是有效字宽 8 而非 12

本脚本对比 4 种布局的背景占比，占比最接近 70% 的才是对的。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "small_cmp2"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]


def save_png(path, arr):
    h, w, _ = arr.shape
    raw = b''.join(b'\x00' + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


def decode16(src, pal=PAL):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += pal[off:off + 2] if off + 1 < len(pal) else b'\x00\x00'
    return bytes(out)


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def segs(code):
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    o = PAGES_SMALL[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        return None
    return [mat8(decode16(zh[o + k * 16:o + k * 16 + 16])) for k in range(4)]


def seg_0x100(code):
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    o = PAGES_SMALL[hi] + lo * 64 - BASE + 0x100
    if o < 0 or o + 16 > N:
        return None
    return mat8(decode16(zh[o:o + 16]))


LAYOUTS = {
    "L1_2x2 (同大字)": lambda s, extra: np.vstack([
        np.hstack([s[0], s[1]]), np.hstack([s[2], s[3]])]),
    "L2_vstack_0_1": lambda s, extra: np.vstack([s[0], s[1]]),
    "L3_hstack_0_1": lambda s, extra: np.hstack([s[0], s[1]]),
    "L4_0_plus_0x100": lambda s, extra: np.vstack([s[0], extra])
    if extra is not None else s[0],
    "L5_concat4_h": lambda s, extra: np.hstack(s),
    "L6_concat4_v": lambda s, extra: np.vstack(s),
}

print("=" * 78)
print("各布局的背景占比（大字基准 70.9%）")
print("=" * 78)
results = {}
for name, fn in LAYOUTS.items():
    bfs = []
    vals = Counter()
    for code in range(0, 256):
        s = segs(code)
        if s is None:
            continue
        ex = seg_0x100(code)
        try:
            m = fn(s, ex)
        except Exception:
            continue
        c = Counter(int(v) for v in m.flatten())
        bg = c.most_common(1)[0][0]
        bfs.append(c[bg] / m.size)
        for v, n in c.items():
            vals[v] += n
    if bfs:
        results[name] = (np.mean(bfs), len(vals), m.shape)
        print(f"  {name:<22} 背景={np.mean(bfs):>6.1%}  值种类={len(vals)}  "
              f"尺寸={m.shape[1]}x{m.shape[0]}")

# 排序，最接近 70.9% 的排最前
print("\n按接近 70.9% 排序：")
for name, (bf, nv, shp) in sorted(results.items(),
                                  key=lambda kv: abs(kv[1][0] - 0.709)):
    print(f"  {name:<22} 背景={bf:.1%}  差={abs(bf-0.709):.1%}")

# 渲染每个布局的前 16 字
print("\n" + "=" * 78)
print("渲染对比（每布局前 16 字）")
print("=" * 78)
for name, fn in LAYOUTS.items():
    mats = []
    for code in range(0, 16):
        s = segs(code)
        if s is None:
            continue
        ex = seg_0x100(code)
        try:
            m = fn(s, ex)
        except Exception:
            continue
        mats.append(m)
    if not mats:
        continue
    h, w = mats[0].shape
    SCALE = 5
    GAP = 3
    cols = 8
    rows = (len(mats) + cols - 1) // cols
    CW = w * SCALE + GAP
    CH = h * SCALE + GAP
    img = np.full((rows * CH, cols * CW, 3), 12, dtype=np.uint8)
    for i, m in enumerate(mats):
        c = Counter(int(v) for v in m.flatten())
        bg = c.most_common(1)[0][0]
        ry, rx = divmod(i, cols)
        y0 = ry * CH + 1
        x0 = rx * CW + 1
        for y in range(h):
            for x in range(w):
                v = int(m[y, x])
                g = 12 if v == bg else (255 if v > bg else 130)
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = (g, g, g)
    p = OUT / f"{name.split()[0]}.png"
    save_png(p, img)
    print(f"  ✔ {p.name}  ({w}x{h})")
