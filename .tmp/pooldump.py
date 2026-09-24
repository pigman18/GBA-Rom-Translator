# -*- coding: utf-8 -*-
"""pooldump.py <tag> <lo> <n> -- 把 VRAM 池区每 2 砖当 1 个 11x11 字，逐列 OCR 出槽号序列，
再按槽号→charmap 反查字符（大字库 1bpp 16B/槽）。

因为 12px 步进 = 2 砖/字（相位两段式），直接按 (t, t+1) 配对取「左 8 列 / 右 3 列」
在相位 0 下成立；相位 4 时第一字占 (t,t+1) 的 4+7 列。这里用退化的稳健办法：
对每个 x 起点滑窗，用 11x11 掩码在字库全库找 d<=1 的槽 —— 同 slotscan.py。
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROOT = Path(r"C:/code/GBA-Rom-Translator")
ROM = (ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000


def mask(s):
    b = ROM[BIG + s * 16: BIG + (s + 1) * 16]
    return tuple((b[(r * 11 + x) >> 3] >> (7 - ((r * 11 + x) & 7))) & 1
                 for r in range(11) for x in range(11))


tag, lo, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
v = (T / f"drive_{tag}_vram.bin").read_bytes()
io = (T / f"drive_{tag}_io.bin").read_bytes()
cbase = ((struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3) * 0x4000

# 把 n 个砖对（2n 个砖）铺成一张 16 行 x (n*8) 列的 4bpp 位图
W = n * 8
band = [[0] * W for _ in range(16)]
for c in range(n):
    for half in (0, 1):
        t = lo + 2 * c + half
        off = cbase + t * 32
        for y in range(8):
            for x in range(8):
                b = v[off + y * 4 + x // 2]
                band[half * 8 + y][c * 8 + x] = (b & 0xF) if x % 2 == 0 else (b >> 4)

print("池 %d..%d（%d 砖对）" % (lo, lo + 2 * n - 1, n))
LIB = [mask(s) for s in range(0x2000)]

for inkv in (1, 8):
    print("\n== 墨色 %d ==" % inkv)
    out = []
    x = 0
    while x <= W - 11:
        obs = tuple(1 if band[2 + r][x + c] == inkv else 0 for r in range(11) for c in range(11))
        nz = sum(obs)
        if nz < 8:
            out.append((x, None, nz))
            x += 1
            continue
        d, s = min((sum(1 for a, b in zip(obs, lib) if a != b), i) for i, lib in enumerate(LIB))
        if d <= 2:
            out.append((x, s, nz))
            x += 11
        else:
            out.append((x, None, nz))
            x += 1
    for (px, s, nz) in out:
        if s is None:
            continue
        col = px // 8
        print("  x=%3d (col%-3d 砖%4d) 槽%04X 墨%d" % (px, col, lo + 2 * col, s, nz))

# 槽号 → 字符：用 charmap.txt 反查（可能过期，仅作提示）
cm = {}
for ln in (ROOT / "configs/POKEMON_RUBY_AXVJ00/charmap.txt").read_text(encoding="utf-8").splitlines():
    if "=" not in ln:
        continue
    hx, ch = ln.split("=", 1)
    try:
        cm[int(hx.strip(), 16)] = ch
    except ValueError:
        pass
print("\n(仅参考) charmap 反查：")
for s in set(s for _, s, _ in out if s is not None):
    print("  槽%04X -> %r" % (s, cm.get(s)))
