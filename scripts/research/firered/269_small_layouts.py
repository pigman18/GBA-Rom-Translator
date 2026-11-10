"""对比小字的两种段布局，看图定胜负。

═══ 我上一轮的错误 ═══
267 导出的小字图是**糊的**（字重叠、横向拖影），我却当成成功。
对比大字 PAGE00（干净可读：中 文 宝 可 梦…），差距明显。

【假设】
  大字：连续 4 段 +0x00/+0x10/+0x20/+0x30，2x2 -> 16x16
  小字：应该也是连续 2 段 +0x00/+0x10，上下 -> 8x16
       （而不是我之前用的 +0x00 和 +0x100 —— 那个 0x100 来自死代码分支和
         配置表的 0x00000100，可能是别的东西）

本脚本渲染两种布局的前 8 个字，直接看图判断。
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
OUT = ROOT / "work" / "_probe" / "small_layouts"
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


def decode16(src):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def segs_of(code):
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    o = PAGES_SMALL[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        return None
    return [mat8(decode16(zh[o + k * 16:o + k * 16 + 16])) for k in range(4)]


LAYOUTS = {
    "A_consec_0_10":      lambda s: np.vstack([s[0], s[1]]),
    "B_0_and_0x100":      None,   # 需要单独读 +0x100，见下
    "C_consec_0_10_wide": lambda s: np.hstack([s[0], s[1]]),
    "D_only_s0":          lambda s: s[0],
    "E_2x2":              lambda s: np.vstack([np.hstack([s[0], s[1]]),
                                              np.hstack([s[2], s[3]])]),
}


def glyph_by_layout(code, name):
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    base = PAGES_SMALL[hi] + lo * 64
    o = base - BASE
    if o < 0:
        return None
    if name == "B_0_and_0x100":
        o1 = o + 0x100
        if o1 + 16 > N:
            return None
        s0 = mat8(decode16(zh[o:o + 16]))
        s1 = mat8(decode16(zh[o1:o1 + 16]))
        return np.vstack([s0, s1])
    segs = segs_of(code)
    if segs is None:
        return None
    return LAYOUTS[name](segs)


def bg_of(m):
    return Counter(int(v) for v in m.flatten()).most_common(1)[0][0]


# ── 渲染每种布局的前 16 个字 ─────────────────────────────
codes = list(range(0, 16))
for name in ("A_consec_0_10", "B_0_and_0x100", "C_consec_0_10_wide",
             "D_only_s0", "E_2x2"):
    mats = []
    for c in codes:
        m = glyph_by_layout(c, name)
        if m is not None:
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
    img = np.full((rows * CH, cols * CW, 3), 14, dtype=np.uint8)
    for i, m in enumerate(mats):
        bg = bg_of(m)
        ry, rx = divmod(i, cols)
        y0 = ry * CH + 1
        x0 = rx * CW + 1
        for y in range(h):
            for x in range(w):
                v = int(m[y, x])
                g = 14 if v == bg else (255 if v > bg else 150)
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = (g, g, g)
    p = OUT / f"{name}.png"
    save_png(p, img)
    print(f"  ✔ {name:<20} {w}x{h}  ->  {p.name}")

    # 同时打印字符画（前 3 个）
    print(f"    前 3 个字符画：")
    for i, m in enumerate(mats[:3]):
        bg = bg_of(m)
        print(f"      码 0x{codes[i]:03X}:")
        for y in range(h):
            print("        " + "".join("." if v == bg else
                                       ("#" if v > bg else "+") for v in m[y]))
