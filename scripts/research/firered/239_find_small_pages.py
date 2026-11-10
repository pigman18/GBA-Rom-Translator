"""追小字的渲染函数 —— 从「谁读小字缓冲」反推字库位置。

═══ 已知 ═══
小字缓冲在 EWRAM（如 0x02001F00），每块 32B 是 8x8 字形。
但 ROM 里搜不到、主字库解不出 ⇒ 小字有自己的页表和 IDX/PAL。

【思路】找「把小字写进 VRAM」的代码
  · VRAM tile 137 = 0x06001120
  · 该 tile 的内容 == EWRAM 0x02001F00 的 32B
  · 所以某段代码执行了：memcpy(0x06001120, 0x02001F00, 32)
  或走 DMA

⇒ 在 ROM 里搜 EWRAM 地址常量 0x02001F00 附近
⇒ 以及 0x02000000 + 0x1F00 的 u32

另一个更强的锚点：**小字也有自己的 PAGES 表**
 主字库 PAGES4 @0x089D08A0（11 项）
 小字的表应该在附近，或者是另一组 11 项/若干项的表

本脚本：
 S1 搜 ROM 里指向「小字页」的常量（原版 FF、汉化有内容的区）
 S2 在小字数据所在区找 6x7 特征块，反推页表
 S3 对比 0x089D08A0 附近是否还有别的页表
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

print("=== S1: 0x089D08A0 附近还有哪些页表 ===")
o = 0x089D0800 - BASE
for i in range(0, 0x200, 16):
    seg = zh[o + i:o + i + 16]
    jseg = ja[o + i:o + i + 16]
    mark = "  ← PAGES4" if 0x089D08A0 - BASE == o + i else ""
    mark += "  ← WIDTH" if 0x089D08D0 - BASE == o + i else ""
    same = " (原版相同)" if seg == jseg else " ★汉化改"
    print(f"  0x{0x089D0800 + i:08X}  {seg.hex(' ')}{mark}{same}")

print("\n=== S2: 用 nibble 特征找「小字页」（6~7 高、nibble 集中）===")
# 小字 tile 的值域
vr = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()
small_vals = set()
for t in (137, 213, 267, 321, 375):
    for b in vr[t * 32:t * 32 + 32]:
        small_vals.add(b & 0xF)
        small_vals.add(b >> 4)
print(f"  小字 tile 的 nibble 值域: {sorted(small_vals)}")

# 但那是解码后的值。ROM 里是索引 v（0..0xFF），再经 IDX 映射。
# 换个角度：小字源数据应该像主字库源那样，是「nibble 种类多但结构规整」的压缩流。
# 直接找「原版 FF、汉化非 FF」的 32KB 连续块，逐个看是否像字库。
print("\n=== S3: 原版 FF、汉化有内容的较大连续块（候选字库页）===")
W = 0x4000
cands = []
for off in range(0, N - W, W):
    seg_z = zh[off:off + W]
    seg_j = ja[off:off + W]
    n_added = sum(1 for a, b in zip(seg_z, seg_j) if b == 0xFF and a != 0xFF)
    if n_added > W * 0.5:
        cands.append((n_added, off))
cands.sort(reverse=True)
print(f"  候选 {len(cands)} 个（新增大半 >50%），前 20:")
for n, off in cands[:20]:
    seg = zh[off:off + W]
    c = Counter(seg)
    ent = -sum((v / W) * np.log2(v / W) for v in c.values())
    print(f"    0x{BASE + off:08X}  新增 {n}/{W} ({n/W:.0%})  值种类 {len(c):>3}  "
          f"熵 {ent:.1f}")

print("\n=== S4: 已知主字库页 vs 这些候选 ===")
known = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
         0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
         0x089B2B0C]
for k in known:
    off = k - BASE
    # 找所属 0x4000 块
    blk = (off // W) * W
    print(f"  页 0x{k:08X} 属于块 0x{BASE + blk:08X}")
