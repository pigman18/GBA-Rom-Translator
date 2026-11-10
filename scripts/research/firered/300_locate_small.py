"""调研(300) 定位小字：从截图量出小字区域，反推它的 tile 与字库。

═══ 用户看图的结论（无可辩驳）═══
队伍界面里有两套字号：
   大字：哈克龙 / 喷火龙 / 喵喵 / 大比鸟 / 请选择宝可梦   （笔画粗）
   小字：Lv44 / Lv50 / HP / 270/287 / 110/110 / PAR      （明显更小更细）

⇒ 必定存在 8x8 的小字字库。我 295 采样失败是因为采样时机不对。

═══ 本脚本：从截图精确定位小字区域 ═══
① 按 3x 图上的坐标换算回 240x160 原图
② 取 "HP 270/287" 那一行（3x 图上约 y=55..75）
③ 量它的字高、字宽
④ 从 tilemap 找出该位置的 tile 序号
⑤ 反查 ROM
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party261"
OUT = ROOT / "work" / "_probe" / "small300"
OUT.mkdir(parents=True, exist_ok=True)

vr = (P / "s01_party01_vram.bin").read_bytes()
SCREEN = 0xF000


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
print(f"截图 {W}x{H}")

# 3x 图上 "HP 270/287" 大约在 y=55..75, x=500..660
# 换算回原图: /3
regions = {
    "HP_270": (168, 18, 222, 26),      # x0,y0,x1,y1 (原图坐标，估计值)
    "Lv44":   (118, 60, 160, 76),
    "PAR":    (172, 32, 200, 42),
}
print("\n=== 裁剪小字区域 ===")
for name, (x0, y0, x1, y1) in regions.items():
    x0 = max(0, min(W - 1, x0)); x1 = max(0, min(W, x1))
    y0 = max(0, min(H - 1, y0)); y1 = max(0, min(H, y1))
    if x1 <= x0 or y1 <= y0:
        continue
    crop = img[y0:y1, x0:x1]
    p = OUT / f"{name}_x{x0}-{x1}_y{y0}-{y1}.png"
    save_png(p, crop.astype(np.uint8), 8)
    print(f"  {name}: ({x0},{y0})..({x1},{y1})  {x1-x0}x{y1-y0} -> {p.name}")

# 量 "HP 270/287" 所在行的墨迹高度（原图 y 60..80 区间）
print("\n=== 逐行墨迹量（原图 y=15..85，x=165..225）===")
sub = img[15:85, 165:225].mean(axis=2)
thr = np.percentile(sub, 85)
ink = sub > thr
for y in range(sub.shape[0]):
    n = int(ink[y].sum())
    if n:
        print(f"  y={15+y:>3}  墨 {n:>2}  " + "#" * n)

# tilemap 0xF000 的行列
print("\n=== tilemap 0xF000 各行的 tile 序号（前 20 列）===")
def ent(r, c):
    return struct.unpack_from('<H', vr, SCREEN + (r * 32 + c) * 2)[0]

for r in range(20):
    ts = [ent(r, c) & 0x3FF for c in range(20)]
    ps = [((ent(r, c) >> 12) & 0xF) for c in range(20)]
    if any(t != 0 for t in ts):
        print(f"  行{r:>2}: tile={ts[:12]} pal={sorted(set(ps))}")
