"""导出小字字库 —— 修正亮度映射。

═══ 257 的问题 ═══
像素值是 0x01/0x02/0x03，而我按「背景=0x11」映射，结果全灰。
实测值分布：1: 6267 / 2: 3352 / 3: 3181
⇒ **1 = 背景，2 = 抗锯齿，3 = 笔画核心**

字 0 的 8x8：
    11111111
    11111231
    11111231
    12222222
    12333233
    12311231
    12311231
    12222222
（清晰的汉字结构）

本脚本用正确映射重出图。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "smallfont"
OUT.mkdir(parents=True, exist_ok=True)


def save_png(path: Path, arr: np.ndarray) -> None:
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


mats = np.load(OUT / "glyphs.npy")
codes = np.load(OUT / "codes.npy")
print(f"字形 {mats.shape}  码位 {codes.shape}")

c = Counter()
for m in mats:
    for v in m.flatten():
        c[int(v)] += 1
print(f"全量值分布: {dict(sorted(c.items()))}")

# 亮度：1=背景(暗) 2=中间(灰) 3=核心(亮)
LUM = {0: (8, 8, 8), 1: (14, 14, 14), 2: (160, 160, 160), 3: (255, 255, 255)}

SCALE = 4
GAP = 2
cols = 32


def render(sel_codes, sel_mats, path: Path, name: str):
    rows = (len(sel_mats) + cols - 1) // cols
    cw, chh = 8 * SCALE + GAP, 8 * SCALE + GAP
    img = np.full((rows * chh, cols * cw, 3), 14, dtype=np.uint8)
    for i, m in enumerate(sel_mats):
        ry, rx = divmod(i, cols)
        y0 = ry * chh + 1
        x0 = rx * cw + 1
        for y in range(8):
            for x in range(8):
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = \
                    LUM.get(int(m[y, x]), (255, 0, 0))
    save_png(path, img)
    print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(sel_mats)} 字)")


render(codes, mats, OUT / "SMALL_ALL.png", "SMALL_ALL.png")

for pi in range(11):
    sel = [(c, m) for c, m in zip(codes, mats) if (int(c) >> 8) == pi]
    if not sel:
        continue
    cs = np.array([x[0] for x in sel], dtype=np.int32)
    ms = np.array([x[1] for x in sel], dtype=np.uint8)
    render(cs, ms, OUT / f"PAGE{pi:02d}.png", f"PAGE{pi:02d}.png")

# 字符画预览前 16 个
print("\n=== 前 16 个字（# = 笔画核心，+ = 抗锯齿）===")
for i in range(min(16, len(mats))):
    code = int(codes[i])
    m = mats[i]
    print(f"\n  码 0x{code:03X}:")
    for y in range(8):
        print("    " + "".join("#" if v == 3 else ("+" if v == 2 else ".")
                               for v in m[y]))
