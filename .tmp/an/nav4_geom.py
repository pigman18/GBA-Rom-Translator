# -*- coding: utf-8 -*-
"""决定性检验：BDF 字形 → 4bpp 字节流 → 在字库 bin 里搜索，反推 bin 的真实几何。"""
import re, numpy as np
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
BDF = ROOT / "fonts/default/Middle.bdf"
BIN = ROOT / "work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle_unshadow(0xE0000).bin"

def parse_bdf(path):
    text = path.read_text("utf-8", errors="replace")
    g = {}
    for m in re.finditer(r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
                         text, re.M | re.S):
        enc = int(m.group(1))
        rows = []
        for line in m.group(2).strip().splitlines():
            line = line.strip()
            if not line:
                continue
            v = int(line, 16)
            rows.append(v)
        g[enc] = rows
    return g

G = parse_bdf(BDF)
print("BDF 字形数:", len(G))
# 行宽统计
from collections import Counter
c = Counter(len(r) for r in G.values())
print("行数分布:", c.most_common(5))
c2 = Counter(len(hex(r)) for r in list(G.values())[0])
print("第一字行 hex 位数:", [len("%X" % r) for r in list(G.values())[0]])

def to_4bpp_8px(rows, y0, nrows):
    """BDF 16bit 行 → 4bpp 字节流（8px 宽，每行 4 字节；低 nibble=左像素）。"""
    out = bytearray()
    for y in range(y0, y0 + nrows):
        H = (rows[y] >> 8) & 0xFF if y < len(rows) else 0   # 高字节 = 列 0..7
        for i in range(4):
            b = 0
            for k in range(2):
                col = 2 * i + k
                bit = (H >> (7 - col)) & 1
                if bit:
                    b |= (0xF << (4 * k))
            out.append(b)
    return bytes(out)

bin_data = np.fromfile(BIN, dtype=np.uint8).tobytes()
print("bin 大小:", len(bin_data), "= %d 字节/字 x %d 字" % (128, len(bin_data)//128))

# 用几个可辨认的字做搜索
for ch in "宝可航员梦领":
    enc = ord(ch)
    if enc not in G:
        print(ch, "不在 BDF"); continue
    rows = G[enc]
    top = to_4bpp_8px(rows, 0, 8)      # 上砖 32B
    bot = to_4bpp_8px(rows, 8, 8)      # 下砖 32B
    full16 = to_4bpp_8px(rows, 0, 16)  # 16 行
    # 1) 搜上砖 32B
    p1 = bin_data.find(top)
    p2 = bin_data.find(top + bot)
    tag = "%-2s U+%04X" % (ch, enc)
    print("\n%s  上砖32B @ %s   上+下64B @ %s" % (
        tag,
        ("%d (gid %d, off %d)" % (p1, p1 // 128, p1 % 128)) if p1 >= 0 else "-",
        ("%d (gid %d, off %d)" % (p2, p2 // 128, p2 % 128)) if p2 >= 0 else "-"))
    # 打印 BDF 原图（列 0..15）
    for y, r in enumerate(rows):
        s = "".join("#" if (r >> (15 - x)) & 1 else "." for x in range(16))
        print("   %2d %s" % (y, s))
