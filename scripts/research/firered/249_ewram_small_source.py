"""追 EWRAM 小字副本 0x02001F08 —— 从这里找小字真实的字库。

═══ 248 的结论 ═══
· IWRAM 0x03003DE0 存的是**主字库大字**（0x03003E60 = 0c 0d = 宽12 高13）
· 小字不在那里
· 小字只在两处：VRAM tile 137 等，和 EWRAM 0x02001F08 / 0x02002898 / 0x02003D08

⇒ 小字是**另一套完全独立的字库**，直接以 4bpp 位图形式存在 EWRAM，
  再由某段代码搬到 VRAM。

本脚本：
 ① 分析 EWRAM 小字区的结构（间隔、总大小）
 ② 在 ROM 里搜「小字区的整体特征」（不是单个 tile，而是整段的模式）
 ③ 找「写 EWRAM 小字区」的代码：搜 0x02001F08 等地址常量
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
vr = (P / "s05_party_vram.bin").read_bytes()
ew = (P / "s05_party_ewram.bin").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

print("=== ① EWRAM 三个小字地址的完整上下文 ===")
for addr in (0x02001F08, 0x02002898, 0x02003D08):
    o = addr - 0x02000000
    print(f"\n  0x{addr:08X} 前 64 / 后 96 字节：")
    for k in range(-64, 96, 32):
        seg = ew[o + k:o + k + 32]
        tag = " ←本块" if k == 0 else ""
        print(f"    {k:+5d}  {seg.hex(' ')}{tag}")

print("\n\n=== ② 在 ROM 里搜 EWRAM 地址常量（找写小字的代码）===")
for target in (0x02001F08, 0x02001F00, 0x02002898, 0x02003D08,
               0x02001E00, 0x02002000, 0x02002800, 0x02003D00):
    nd = struct.pack('<I', target)
    pos = zh.find(nd)
    hits = []
    while pos >= 0:
        hits.append(BASE + pos)
        pos = zh.find(nd, pos + 1)
    print(f"  0x{target:08X}: {len(hits)} 处 {[hex(h) for h in hits[:6]]}")

print("\n=== ③ EWRAM 中间隔 0xA00 的模式：0x02001F08 / 0x02002898 / 0x02003D08 ===")
ds = [0x02002898 - 0x02001F08, 0x02003D08 - 0x02002898]
print(f"  间隔: {[hex(d) for d in ds]}")

print("\n=== ④ 用「小字整段」去 ROM 搜：取 0x02001F00 起 0x100 字节 ===")
seg = ew[0x02001F00 - 0x02000000:0x02001F00 - 0x02000000 + 0x100]
p = zh.find(seg)
print(f"  256B 整段命中: {'0x%08X' % (BASE + p) if p >= 0 else '-'}")
# 分段搜
for ln in (128, 64, 32):
    cnt = 0
    for k in range(0, 0x100 - ln, 16):
        if zh.find(seg[k:k + ln]) >= 0:
            cnt += 1
    print(f"  {ln}B 子段命中 {cnt} 个")

print("\n=== ⑤ 小字是否来自原版 ROM 的 ASCII/假名 8x8 字体 ===")
# 原版火红的 8x8 字体区通常在 0x08xxxxxx 的某处
# 试：把小字 nibble 归一化到 0/1（墨迹），去原版搜
def to_1bpp(blob, bg=0x55, thresh=None):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    out = bytearray()
    for y in range(8):
        b = 0
        for x in range(8):
            if m[y, x] != bg:
                b |= 1 << (7 - x)
        out.append(b)
    return bytes(out)


for t in (137, 213, 375):
    blob = vr[t * 32:t * 32 + 32]
    m1 = to_1bpp(blob, bg=0x05)
    pz = zh.find(m1)
    pj = ja.find(m1)
    print(f"  tile {t}: 1bpp={m1.hex()}  "
          f"汉化={'0x%08X' % (BASE+pz) if pz>=0 else '-'}  "
          f"原版={'0x%08X' % (BASE+pj) if pj>=0 else '-'}")

print("\n=== ⑥ 小字区的整体画像（0x02001F00 起 0x1000）===")
seg2 = ew[0x02001F00 - 0x02000000:0x02001F00 - 0x02000000 + 0x1000]
c = Counter(seg2)
print(f"  值种类 {len(c)}，最常见 {[(f'0x{k:02X}', v) for k, v in c.most_common(8)]}")
print(f"  非零 {sum(1 for b in seg2 if b)}/0x1000")
