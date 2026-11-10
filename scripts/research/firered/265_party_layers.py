"""从队伍界面的 tilemap 找真正的文字 tile。

═══ 关键教训 ═══
我一直在分析 VRAM tile 137/213/267，但截图显示队伍界面左侧是**宝可梦图标**，
tile 137 解出来是「满格方块」= 图标，不是文字。

⇒ 必须先找到队伍界面的 tilemap，才能知道哪些 tile 是文字。

DISPCNT = 0x1740（队伍界面）
  bit0-2 BG mode, bit8-11 BG enable, bit12 OBJ

本脚本：
 ① 解析 DISPCNT/BGxCNT，得到每层的 screenBase/charBase
 ② 按真实配置渲染每层，肉眼看哪层是文字
 ③ 从文字层提取 tile 序号
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party261"
vr = (P / "s01_party01_vram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
OUT = ROOT / "work" / "_probe" / "party_layers"
OUT.mkdir(parents=True, exist_ok=True)


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


# ── 读 IO（IWRAM 里没有 IO，但我们知道 DISPCNT=0x1740）
# BGxCNT 需要从 IO 读，Lua 的 readRange(0x04000000) 从 +0x10 起是假数据
# 但 +0x00..+0x10 可信：DISPCNT(0x00) BG0CNT(0x08) BG1CNT(0x0A) BG2CNT(0x0C) BG3CNT(0x0E)
# 261 没存 io.bin，重新从 iwram 找不到。改用「穷举 BG 配置渲染」的办法。

DISPCNT = 0x1740
print(f"DISPCNT = 0x{DISPCNT:04X}")
print(f"  BG mode = {DISPCNT & 7}")
print(f"  BG enable: BG0={bool(DISPCNT & 0x100)} BG1={bool(DISPCNT & 0x200)} "
      f"BG2={bool(DISPCNT & 0x400)} BG3={bool(DISPCNT & 0x800)}")
print(f"  OBJ = {bool(DISPCNT & 0x1000)}")


def mat(blob, bpp=4):
    if bpp == 4:
        m = np.zeros((8, 8), dtype=np.uint8)
        for y in range(8):
            for x in range(8):
                v = blob[y * 4 + x // 2]
                m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
        return m
    else:  # 8bpp
        m = np.zeros((8, 8), dtype=np.uint8)
        for y in range(8):
            for x in range(8):
                m[y, x] = blob[y * 8 + x]
        return m


def render_layer(sb, cb, bpp, chars=32, rows=20):
    img = np.zeros((rows * 8, chars * 8), dtype=np.uint8)
    for r in range(rows):
        for c in range(chars):
            o = sb + (r * chars + c) * 2
            if o + 2 > len(vr):
                continue
            e = struct.unpack_from('<H', vr, o)[0]
            t = e & 0x3FF
            hf = (e >> 10) & 1
            vf = (e >> 11) & 1
            to = cb + t * (32 if bpp == 4 else 64)
            if to + (32 if bpp == 4 else 64) > len(vr):
                continue
            m = mat(vr[to:to + (32 if bpp == 4 else 64)], bpp)
            if hf:
                m = m[:, ::-1]
            if vf:
                m = m[::-1, :]
            img[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8] = m
    return img


# 穷举所有 (sb, cb, bpp)，用「文字特征」评分：
# 文字特征 = 8x8 块内非零像素中等（不空不满），且值种类 <= 4
print("\n穷举 (screenBase, charBase, bpp) 找文字层...")
best = []
for sb in range(0, 0x10000, 0x800):
    for cb in (0x0000, 0x4000, 0x8000, 0xC000):
        for bpp in (4, 8):
            n_text = 0
            for r in range(20):
                for c in range(30):
                    o = sb + (r * 32 + c) * 2
                    if o + 2 > len(vr):
                        continue
                    e = struct.unpack_from('<H', vr, o)[0]
                    t = e & 0x3FF
                    if t == 0:
                        continue
                    to = cb + t * (32 if bpp == 4 else 64)
                    if to + (32 if bpp == 4 else 64) > len(vr):
                        continue
                    m = mat(vr[to:to + (32 if bpp == 4 else 64)], bpp)
                    vals = len(set(int(v) for v in m.flatten()))
                    nz = int((m != 0).sum())
                    if vals <= 4 and 8 <= nz <= 40:
                        n_text += 1
            if n_text:
                best.append((n_text, sb, cb, bpp))

best.sort(reverse=True)
print(f"  有结果的配置 {len(best)} 个，前 10：")
for n, sb, cb, bpp in best[:10]:
    print(f"    sb=0x{sb:04X} cb=0x{cb:04X} bpp={bpp}: 文字tile {n}")

# 渲染前 4 个
for i, (n, sb, cb, bpp) in enumerate(best[:4]):
    img = render_layer(sb, cb, bpp)
    # 放大 2x，灰度
    img2 = np.repeat(np.repeat(img, 2, axis=0), 2, axis=1)
    rgb = np.stack([img2 * 17] * 3, axis=-1).astype(np.uint8)
    p = OUT / f"L{i}_sb{sb:04X}_cb{cb:04X}_{bpp}bpp.png"
    save_png(p, rgb)
    print(f"  ✔ {p.name}")
