"""调研(299) 在局部区域逐像素量文字的纵向墨迹跨度。

═══ 298 的不足 ═══
整行 std 只能看出「界面块」，分不出单个字的高度。

═══ 新方法 ═══
队伍界面每只宝可梦占一个信息块，块内名字（中文）和等级（Lv44）同一行。
取「名字」那一小段区域，逐列算墨迹的 y 范围：
    8 高  -> 8x8 瓦片字
    12+ 高 -> 大字

同时把该区域放大输出，直接看图。
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party261"
OUT = ROOT / "work" / "_probe" / "measure299"
OUT.mkdir(parents=True, exist_ok=True)


def read_png(path: Path):
    data = path.read_bytes()
    o = 8
    width = height = colortype = None
    idat = b""
    while o < len(data):
        ln = struct.unpack_from(">I", data, o)[0]
        typ = data[o + 4:o + 8]
        body = data[o + 8:o + 8 + ln]
        o += 12 + ln
        if typ == b"IHDR":
            width, height, bd, colortype = struct.unpack_from(">IIBB", body)[0:4]
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    raw = zlib.decompress(idat)
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colortype]
    stride = width * ch
    out = np.zeros((height, width, ch), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.uint8)
    pos = 0
    for y in range(height):
        f = raw[pos]; pos += 1
        line = np.frombuffer(raw[pos:pos + stride], dtype=np.uint8).astype(np.int16)
        pos += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif f == 2:
            line = (line + prev) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + int(prev[i])) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = int(line[i - ch]) if i >= ch else 0
                b = int(prev[i]); c = int(prev[i - ch]) if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y] = line.reshape(width, ch).astype(np.uint8)
        prev = line.astype(np.uint8)
    return out[:, :, :3] if ch >= 3 else np.repeat(out, 3, axis=2)


def save_png(path: Path, arr: np.ndarray, scale: int = 1) -> None:
    if scale > 1:
        arr = np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1)
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


img = read_png(P / "s01_party01.png")
H, W, _ = img.shape
gray = img.mean(axis=2)

# 放大整屏供肉眼核对
save_png(OUT / "screen_x3.png", img.astype(np.uint8), 3)
print(f"截图 {W}x{H}，已放大 3x 输出 {OUT / 'screen_x3.png'}")

# 文字是浅色（高亮），背景是深色。取亮度前 20% 作为「墨」
thr = np.percentile(gray, 88)
print(f"墨阈值（88 分位）= {thr:.0f}")
ink = gray > thr

# 逐列统计墨迹纵向跨度
print("\n=== 每列的墨迹纵向跨度（只列出有墨的列段）===")
col_h = np.zeros(W, dtype=int)
col_top = np.zeros(W, dtype=int)
col_bot = np.zeros(W, dtype=int)
for x in range(W):
    ys = np.flatnonzero(ink[:, x])
    if len(ys):
        col_h[x] = ys[-1] - ys[0] + 1
        col_top[x] = ys[0]
        col_bot[x] = ys[-1]

# 找出「连续有墨的列段」= 一个文字串
segs = []
cur = []
for x in range(W):
    if col_h[x] > 0:
        cur.append(x)
    else:
        if len(cur) >= 6:
            segs.append((cur[0], cur[-1]))
        cur = []
if len(cur) >= 6:
    segs.append((cur[0], cur[-1]))

print(f"\n找到 {len(segs)} 个文字段：")
for x0, x1 in segs[:20]:
    hs = col_h[x0:x1 + 1]
    top = col_top[x0:x1 + 1][hs > 0]
    bot = col_bot[x0:x1 + 1][hs > 0]
    h = int(bot.max() - top.min() + 1) if len(top) else 0
    tag = ""
    if h <= 9:
        tag = "  ← 8~9 高"
    elif 10 <= h <= 14:
        tag = "  ← 10~14 高"
    print(f"  x={x0:>3}..{x1:>3}  宽 {x1 - x0 + 1:>2}  纵向墨迹 {h:>2}{tag}")

# 裁剪几个文字段放大
print("\n裁剪放大：")
for i, (x0, x1) in enumerate(segs[:4]):
    pad = 2
    y0 = max(0, int(col_top[x0:x1 + 1][col_h[x0:x1 + 1] > 0].min()) - pad)
    y1 = min(H, int(col_bot[x0:x1 + 1][col_h[x0:x1 + 1] > 0].max()) + pad + 1)
    crop = img[y0:y1, max(0, x0 - pad):min(W, x1 + pad + 1)]
    p = OUT / f"seg{i}_x{x0}-{x1}.png"
    save_png(p, crop.astype(np.uint8), 6)
    print(f"  seg{i}: x={x0}..{x1} y={y0}..{y1} -> {p.name}")
