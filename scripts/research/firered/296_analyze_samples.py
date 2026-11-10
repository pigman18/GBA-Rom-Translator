"""分析 295 抓到的 400 条字形缓冲采样。"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "glyphs295"
data = (P / "samples.bin").read_bytes()
REC = 130
n = len(data) // REC
print(f"采样 {n} 条")

# 每条：128B 位图 + 2B 宽高
recs = []
for i in range(n):
    buf = data[i * REC:(i + 1) * REC - 2]
    wh = data[(i + 1) * REC - 2:(i + 1) * REC]
    recs.append((buf, wh[0], wh[1]))

print("\n=== 宽高分布（0x03003E60 的 2 字节）===")
whc = Counter((w, h) for _, w, h in recs)
for (w, h), c in whc.most_common(10):
    print(f"  宽=0x{w:02X}({w})  高=0x{h:02X}({h})  x{c}")

# 去重位图
uniq = {}
for buf, w, h in recs:
    uniq.setdefault(buf, (w, h, 0))
    ww, hh, cc = uniq[buf]
    uniq[buf] = (ww, hh, cc + 1)
print(f"\n不同位图 {len(uniq)} 种")

# 有内容的位图
print("\n=== 有内容的位图（前 8 个）===")
shown = 0
for buf, (w, h, c) in uniq.items():
    # 4bpp 8x8
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = buf[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    vals = Counter(int(v) for v in m.flatten())
    bg = vals.most_common(1)[0][0]
    ink = int((m != bg).sum())
    if ink < 4:
        continue
    shown += 1
    print(f"\n  宽=0x{w:02X}({w}) 高=0x{h:02X}({h})  出现 {c} 次  墨={ink}")
    for y in range(8):
        print("    " + "".join("." if v == bg else "#" for v in m[y]))
    if shown >= 8:
        break

# 按宽分组，统计各自有几张有内容的图
print("\n=== 按宽度分组，有内容位图数 ===")
by_w = {}
for buf, (w, h, c) in uniq.items():
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = buf[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    vals = Counter(int(v) for v in m.flatten())
    bg = vals.most_common(1)[0][0]
    ink = int((m != bg).sum())
    if ink < 4:
        continue
    by_w.setdefault(w, []).append((buf, h, ink))
for w in sorted(by_w):
    print(f"  宽 0x{w:02X}({w}): {len(by_w[w])} 张有内容")
