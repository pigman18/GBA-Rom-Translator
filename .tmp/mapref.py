# -*- coding: utf-8 -*-
"""mapref.py <tag> <bg> — 打印该 BG 引用的**全部** tile 号（排序），并标注绝对字节与所属 16KB 块"""
import re, sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, bg = sys.argv[1], int(sys.argv[2])
txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
reg = {}
for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt):
    reg[m.group(1)] = int(m.group(2), 16)
cnt = reg["BG%dCNT" % bg]
cb = (cnt >> 2) & 3
sb = (cnt >> 8) & 0x1F
mapaddr = 0x06000000 + sb * 0x800
base = 0x06000000 + cb * 0x4000
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
m8 = v[mapaddr - 0x06000000:mapaddr - 0x06000000 + 0x800]
seen = {}
for i in range(0x400):
    w = m8[i * 2] | (m8[i * 2 + 1] << 8)
    if w == 0:
        continue
    t = w & 0x3FF
    seen.setdefault(t, []).append(i)
nums = sorted(seen)
print("%s BG%d CNT=0x%04X cb=%d sb=%d map=0x%08X 引用 %d 号" % (tag, bg, cnt, cb, sb, mapaddr, len(nums)))
lows = sorted(n for n in nums if n < 512)
high = sorted(n for n in nums if 512 <= n < 896)
over = sorted(n for n in nums if n >= 896)
def rng(l):
    if not l: return "-"
    out, s, p = [], l[0], l[0]
    for x in l[1:]:
        if x == p + 1: p = x; continue
        out.append("%d-%d" % (s, p) if s != p else "%d" % s); s = p = x
    out.append("%d-%d" % (s, p) if s != p else "%d" % s)
    return " ".join(out)
print("  <512 : %s" % rng(lows))
print("  512-895: %s" % rng(high))
print("  >=896: %s" % rng(over))
# 各号内容非零字节数
def nz(t):
    off = base + t * 32 - 0x06000000
    return sum(1 for x in v[off:off + 32] if x)
print("  --- 逐号 (号:nz字节:引用格数) ---")
line = []
for t in nums:
    line.append("%d:%d/%d" % (t, nz(t), len(seen[t])))
print("  " + "  ".join(line))
