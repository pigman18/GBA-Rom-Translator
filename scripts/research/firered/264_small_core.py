"""修正理解：小字是 6 宽 × 8 高，两侧/底部有背景填充。

═══ 263/264 的关键观察 ═══
tile 137（VRAM 直读 4bpp）：
    55BBBC55
    5BCBCBC5
    5CCBCCC5
    55BBB555
    5BCCCBC5
    5BC55BC5
    5CBBBCC5
    55CCCC55
⇒ **左右两侧的 5 是背景**，中间 6 列（x=1..6）才是字。
⇒ 字实际是 **6 宽 × 8 高**。

tile 213/267/321（同一个字，出现 3 次）：
    4BCBCBC4
    5CCBCCC5
    44BBB444
    4BCCCBC4
    4BC44BC4
    4CBBBCC4
    888CCCC88
    11111111
⇒ 左右 4/5，底部 88/11 是**列表项的分隔装饰**。

⇒ 结论：VRAM 里的小字 tile 混了 UI 装饰。
   真正的字形要**去掉边缘填充**。

本脚本：
 ① 去边取 6x8 核心
 ② 用核心的墨迹掩码在 ROM 里搜（6 宽 => 每行 1 字节够）
 ③ 定位小字在 ROM 的存储
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


print("=== 去边后的 6x8 核心 ===")
cores = {}
for t in (137, 213, 267, 321, 375):
    m = mat(vr[t * 32:t * 32 + 32])
    # 按值分布判断背景值（占比最大的）
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    # 去左右各 1 列、底部 1~2 行
    core = m[0:7, 1:7]
    cores[t] = (core, bg)
    print(f"\n  tile {t} 背景值={bg:X}")
    for y in range(7):
        print("    " + "".join("#" if core[y, x] not in (bg, 0) else "."
                               for x in range(6)))

# 用核心墨迹（6 宽，每行 1 字节的高 6 位）搜 ROM
print("\n\n=== 用 6 宽墨迹掩码搜 ROM ===")


def mask6x7(core, bg):
    out = bytearray()
    for y in range(7):
        b = 0
        for x in range(6):
            if core[y, x] not in (bg, 0):
                b |= 1 << (7 - x)
        out.append(b)
    return bytes(out)


results = []
for t, (core, bg) in cores.items():
    mk = mask6x7(core, bg)
    p = zh.find(mk)
    hits = []
    while p >= 0 and len(hits) < 5:
        hits.append(BASE + p)
        p = zh.find(mk, p + 1)
    pj = ja.find(mk)
    results.append((t, mk.hex(), hits, BASE + pj if pj >= 0 else None))
    print(f"\n  tile {t}: mask={mk.hex()}")
    print(f"    汉化: {[hex(h) for h in hits]}")
    print(f"    原版: {'0x%08X' % (BASE + pj) if pj >= 0 else '-'}")

# 也搜 8 行的完整（含底部装饰行）
print("\n=== 8 宽 8 行的完整掩码 ===")
for t in (137, 213, 375):
    m = mat(vr[t * 32:t * 32 + 32])
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    mk = bytes(sum((1 << (7 - x)) for x in range(8) if m[y, x] not in (bg, 0))
               for y in range(8))
    p = zh.find(mk)
    print(f"  tile {t} bg={bg:X}: mask={mk.hex()}  汉化={'0x%08X' % (BASE+p) if p>=0 else '-'}")

# 关键：小字的 4bpp 值域是 {1,4,5,8,B,C}
# 这是「调色板索引」，说明小字用**独立的调色板**（不是 PAL 表）
# 找那张调色板的 16 项：应该在 IWRAM 或 VRAM 调色板区
print("\n\n=== 找小字的调色板（VRAM 调色板区 0x05000000）===")
pal_vram = (P / "s01_party01_pal.bin").read_bytes()
print(f"  VRAM 调色板 1024 字节，按 16 色一组共 16 组：")
for g in range(16):
    seg = pal_vram[g * 32:(g + 1) * 32]
    print(f"    组{g:>2}: {seg[:16].hex(' ')}")

# 小字用 1/4/5/8/B/C 这些索引，看哪组调色板在这些索引上有明显区分
print("\n  哪组调色板在索引 1,4,5,8,B,C 上颜色分明：")
for g in range(16):
    seg = pal_vram[g * 32:(g + 1) * 32]
    vals = []
    for idx in (1, 4, 5, 8, 0xB, 0xC):
        lo = seg[idx * 2] | (seg[idx * 2 + 1] << 8)
        vals.append(lo)
    uniq = len(set(vals))
    print(f"    组{g:>2}: {uniq} 种不同颜色  {[hex(v) for v in vals[:6]]}")
