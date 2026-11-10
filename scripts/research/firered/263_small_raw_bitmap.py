"""小字是直接存储的 4bpp 位图 —— 用「归一化墨迹掩码」在 ROM 里搜。

═══ 262 的决定性结论 ═══
tile 137 的 16 个像素对**没有一个**在 PAL 里（PAL 最大项是 `21 33`，
而小字是 `55bb`/`b5bc`/`cc5c` 这类）。
⇒ 小字**不经过 IDX/PAL 解码**，是直接存的位图。

小字的 4bpp nibble 值域：{1,4,5,8,11,12}（早前统计）
其中 5 出现最多（背景），b/c 是笔画。
⇒ 这不是 GBA 标准的 0=透明 约定，而是**自定义的 4bpp 调色板索引**。

本脚本：
 ① 把 tile 137 等按 4bpp 直读，确认形状确实是小字（已知成立）
 ② 提取「墨迹掩码」：nibble != 5 视为墨，每行 1 字节 -> 8 字节
 ③ 在 ROM 全量搜这个 8 字节掩码
 ④ 若命中，说明 ROM 里就是这份数据（可能是不同调色板索引）
 ⑤ 换多种「背景值」假设重试
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)
P = ROOT / "work" / "_probe" / "party261"
vr = (P / "s01_party01_vram.bin").read_bytes()


def mat(blob, w=8, h=8):
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


targets = [137, 213, 267, 321, 375]
print("=== 小字 tile 的 4bpp 直读 ===")
for t in targets:
    m = mat(vr[t * 32:t * 32 + 32])
    vals = Counter(int(v) for v in m.flatten())
    print(f"\n  tile {t} 值={dict(sorted(vals.items()))}")
    for y in range(8):
        print("    " + "".join(f"{v:X}" for v in m[y]))

print("\n\n=== 用墨迹掩码（8 字节）在 ROM 里搜 ===")
def mask8(m, bg):
    out = bytearray()
    for y in range(8):
        b = 0
        for x in range(8):
            if m[y, x] != bg:
                b |= 1 << (7 - x)
        out.append(b)
    return bytes(out)


for bg in (5, 1, 4, 8, 11, 0, 0xF):
    n_hit = 0
    detail = []
    for t in targets:
        m = mat(vr[t * 32:t * 32 + 32])
        mk = mask8(m, bg)
        p = zh.find(mk)
        if p >= 0:
            n_hit += 1
            detail.append((t, BASE + p, mk.hex()))
    print(f"  背景值 {bg:X}: 命中 {n_hit}/{len(targets)}")
    for t, a, h in detail[:3]:
        print(f"    tile {t} -> 0x{a:08X}  mask={h}")

# 也搜 32B 原样（换调色板索引）
print("\n=== 原样 32B 搜（含所有可能的索引置换）===")
for t in targets[:2]:
    blob = vr[t * 32:t * 32 + 32]
    p = zh.find(blob)
    print(f"  tile {t}: {'0x%08X' % (BASE + p) if p >= 0 else '-'}")

# 关键：小字的调色板在哪？搜包含 55/bb/cb 等值的表
print("\n=== 找小字的调色板（含 55 bb cb b5 bc 等 nibble 的表）===")
need_nibs = {5, 0xb, 0xc, 0x4, 0x8, 0x1}
best = []
for off in range(0, N - 64, 4):
    seg = zh[off:off + 64]
    vals = set()
    for b in seg:
        vals.add(b & 0xF)
        vals.add(b >> 4)
    if need_nibs <= vals and len(vals) <= 8:
        best.append((len(vals), BASE + off))
print(f"  候选 {len(best)} 个，前 10（值域最小者优先）：")
for nv, a in sorted(best)[:10]:
    o = a - BASE
    print(f"    0x{a:08X} 值种类={nv}  {zh[o:o+16].hex(' ')}")

# 检查原版是否也有
print("\n=== 同上，在原版 ROM 里 ===")
best2 = []
for off in range(0, len(ja) - 64, 4):
    seg = ja[off:off + 64]
    vals = set()
    for b in seg:
        vals.add(b & 0xF)
        vals.add(b >> 4)
    if need_nibs <= vals and len(vals) <= 8:
        best2.append((len(vals), BASE + off))
print(f"  原版候选 {len(best2)} 个")
