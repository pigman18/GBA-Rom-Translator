"""调研(298) 直接测量队伍界面截图里文字的像素高度。

═══ 用户的论点（决定性的）═══
GBA 显示字的原理是瓦片（8x8）。要从 12x12 的字库得到 8x8 的字，
除非实现一套缩放算法 —— 那不值得消耗资源。

⇒ **如果队伍界面真的显示 8x8 的字，就必须有一套 8x8 的字库数据。**

═══ 我之前错在哪 ═══
295/297 采样 0x03003DE0 得到 400 帧相同的位图（宽12高13），
那是「最后一次绘制」的残留，不是队伍界面正在绘制的字。

═══ 本脚本：不猜采样点，直接量屏幕 ═══
① 读队伍界面截图（240x160）
② 找文字行，测每个字符的实际像素高度
③ 8 高 = 8x8 瓦片字；12+ 高 = 大字
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party261"


def read_png(path: Path):
    """最小 PNG 解码（8 位 RGB/RGBA，无交错）。"""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    o = 8
    width = height = bitdepth = colortype = None
    idat = b""
    while o < len(data):
        ln = struct.unpack_from(">I", data, o)[0]
        typ = data[o + 4:o + 8]
        body = data[o + 8:o + 8 + ln]
        o += 12 + ln
        if typ == b"IHDR":
            width, height, bitdepth, colortype = struct.unpack_from(">IIBB", body)[0:4]
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
        f = raw[pos]
        pos += 1
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
                b = int(prev[i])
                c = int(prev[i - ch]) if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y] = line.reshape(width, ch).astype(np.uint8)
        prev = line.astype(np.uint8)
    return out[:, :, :3] if ch >= 3 else np.repeat(out, 3, axis=2)


img = read_png(P / "s01_party01.png")
print(f"截图 {img.shape}")

# 转灰度
gray = img.mean(axis=2).astype(np.uint8)
print(f"灰度范围 {gray.min()}..{gray.max()}")

# 找「文字行」：对比度高的行
row_std = gray.std(axis=1)
print("\n=== 每行对比度（std>12 视为有内容）===")
for y in range(gray.shape[0]):
    if row_std[y] > 12:
        print(f"  行{y:>3}: std={row_std[y]:.1f}")

# 聚合成文字带
print("\n=== 文字带（连续高对比行）===")
bands = []
cur = []
for y in range(gray.shape[0]):
    if row_std[y] > 10:
        cur.append(y)
    else:
        if cur:
            bands.append((cur[0], cur[-1]))
            cur = []
if cur:
    bands.append((cur[0], cur[-1]))

for y0, y1 in bands:
    h = y1 - y0 + 1
    tag = ""
    if h <= 9:
        tag = "  ← 8px 级（小字瓦片）"
    elif 10 <= h <= 14:
        tag = "  ← 12px 级（大字）"
    print(f"  y={y0}..{y1}  高 {h}{tag}")
