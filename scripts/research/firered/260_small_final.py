"""导出小字字库 —— 最终正确版本（noshift 读序 + 8x8）。

═══ 259 的决定性发现 ═══
decode16 有两种读序：
  · swap   ：src[1], src[0], src[3], src[2]...（我按反汇编理解的）
  · noshift：src[0], src[1], src[2], src[3]...（顺序读）

实测「中」字（码 0x000）：
  noshift 版：
      ........
      .+#.....
      .+#.....
      ++++.+++
      #+##.+##
      .+#..+#.
      .+#..+#.
      ++++.+++
  ⇒ 完全正确！竖线在中，方框完整。

  swap 版：
      ........
      .....+#.
      .....+#.
      .+++++++
      .+###+##
      .+#..+#.
      .+#..+#.
      .+++++++
  ⇒ 水平镜像/错位，不对。

⇒ **小字用顺序读（noshift），主字库用交换读（swap）**。
  两个分支确实是两套逻辑。

本脚本按 noshift 导出全部 2816 个小字。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "smallfont_final"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]
STRIDE = 64
SEG = 16
MAXCODE = 0x0AFF


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


def decode_noshift(src: bytes) -> bytes:
    """顺序读：第 r3 个 v = src[r3]。"""
    out = bytearray()
    for r3 in range(16):
        v = src[r3] if r3 < len(src) else 0
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def mat8(blob32: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob32[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def small_glyph(code: int) -> np.ndarray | None:
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    a = PAGES_SMALL[hi] + lo * STRIDE
    o = a - BASE
    if o < 0 or o + SEG > N:
        return None
    return mat8(decode_noshift(zh[o:o + SEG]))


print("=== 导出全部小字（noshift，8x8）===")
items = []
for code in range(MAXCODE + 1):
    m = small_glyph(code)
    if m is None:
        continue
    ink = int((m >= 2).sum())
    if ink < 3:
        continue
    items.append((code, m, ink))
print(f"  有内容码位 {len(items)}")

vals = Counter()
for _, m, _ in items:
    for v in m.flatten():
        vals[int(v)] += 1
print(f"  像素值分布: {dict(sorted(vals.items()))}")

SCALE = 4
GAP = 2
cols = 32
LUM = {0: (8, 8, 8), 1: (14, 14, 14), 2: (170, 170, 170), 3: (255, 255, 255)}


def render(ms, path: Path, name: str):
    rows = (len(ms) + cols - 1) // cols
    cw, chh = 8 * SCALE + GAP, 8 * SCALE + GAP
    img = np.full((rows * chh, cols * cw, 3), 14, dtype=np.uint8)
    for i, m in enumerate(ms):
        ry, rx = divmod(i, cols)
        y0 = ry * chh + 1
        x0 = rx * cw + 1
        for y in range(8):
            for x in range(8):
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = \
                    LUM.get(int(m[y, x]), (255, 0, 0))
    save_png(path, img)
    print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(ms)} 字)")


render([m for _, m, _ in items], OUT / "SMALL_ALL.png", "SMALL_ALL.png")

for pi in range(11):
    sel = [(c, m) for c, m, _ in items if (c >> 8) == pi]
    if not sel:
        continue
    render([m for _, m in sel], OUT / f"PAGE{pi:02d}.png", f"PAGE{pi:02d}.png")

arr = np.zeros((len(items), 8, 8), dtype=np.uint8)
for i, (_, m, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _ in items], dtype=np.int32))
print(f"\n已存 glyphs.npy {arr.shape}")

print("\n=== 前 8 个字 ===")
for i in range(min(8, len(items))):
    code = items[i][0]
    m = items[i][1]
    print(f"\n  码 0x{code:03X}:")
    for y in range(8):
        print("    " + "".join("#" if v == 3 else ("+" if v == 2 else ".")
                               for v in m[y]))

print("\n=== 各页原版状态 ===")
for pi, pg in enumerate(PAGES_SMALL):
    o = pg - BASE
    nf = sum(1 for b in ja[o:o + 0x4000] if b == 0xFF)
    print(f"  页{pi} 0x{pg:08X}: 原版 FF={nf}/16384 ({nf/0x4000:.1%})")
