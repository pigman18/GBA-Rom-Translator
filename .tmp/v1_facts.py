# -*- coding: utf-8 -*-
"""v1_facts.py — v1 8px 渲染层开工前的三个「必须核准」事实（只读，不改任何东西）：

  A. 池 [521,1024) 是否真的没人引用（hirefs 同逻辑，阈值放宽到 384 以便看空档起点）
  B. Middle 4bpp 字模真实布局（128B/字：色值分布、墨迹列/行范围、上下半砖切分）
  C. EWRAM 我方状态区可用字节数（dump 里连续零 + 全 ROM 无字面量引用）
"""
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROOT = Path(r"C:/code/GBA-Rom-Translator")
VRAM = 0x06000000
FONTMID = ROOT / "work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle_unshadow(0xE0000).bin"
ROMF = ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba"

print("=" * 78)
print("A. 各 dump 里 BG map 引用号 >=384 的层（看空档从哪开始）")
print("=" * 78)
worst = 0
for vp in sorted(T.glob("drive_*_vram.bin")):
    tag = vp.stem.replace("drive_", "")
    ip = T / ("drive_%s_io.bin" % tag)
    lp = T / ("drive_%s.log" % tag)
    d = {}
    if ip.exists():
        ib = ip.read_bytes()
        d["DISPCNT"] = struct.unpack_from("<H", ib, 0)[0]
        for i in range(4):
            d["BG%dCNT" % i] = struct.unpack_from("<H", ib, 0x08 + 2 * i)[0]
    elif lp.exists():
        import re
        txt = lp.read_text(encoding="utf-8", errors="replace")
        d = {m.group(1): int(m.group(2), 16)
             for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt)}
    if not d:
        continue
    v = vp.read_bytes()
    dis = d.get("DISPCNT", 0)
    for b in range(4):
        if not ((dis >> (8 + b)) & 1):
            continue
        if b >= 2 and (dis & 7) != 0:
            continue
        cnt = d.get("BG%dCNT" % b, 0)
        sb, sz = (cnt >> 8) & 0x1F, (cnt >> 14) & 3
        hi = set()
        for i in range((32 << sz) * 32):
            o = sb * 0x800 + i * 2
            if o + 2 <= len(v):
                n = struct.unpack_from("<H", v, o)[0] & 0x3FF
                if n >= 384:
                    hi.add(n)
        if hi:
            mx = max(hi)
            worst = max(worst, mx)
            print("  %-16s BG%d  >=384 共 %3d 种，min=%d max=%d" % (tag, b, len(hi), min(hi), mx))
print("  >>> 全部 dump 里出现过的最大引用号 = %d" % worst)

print()
print("=" * 78)
print("B. Middle 4bpp 字模布局实测（%s）" % FONTMID.name)
print("=" * 78)
fb = FONTMID.read_bytes()
print("  文件大小 = %d 字节 = %d 字 × 128B" % (len(fb), len(fb) // 128))


def nibbles(cell):
    """返回 16 行 × 16 列 的 nibble 矩阵（tile 布局 [TL][BL][TR][BR]，每 tile 8x8）。"""
    g = [[0] * 16 for _ in range(16)]
    # tile t(0..3): 抖 8x8；t0=左上(行0-7,列0-7) t1=左下(行8-15,列0-7) t2=右上 t3=右下
    for t in range(4):
        base = t * 32
        r0 = 0 if t in (0, 2) else 8
        c0 = 0 if t in (0, 1) else 8
        for y in range(8):
            for xb in range(4):
                byte = cell[base + y * 4 + xb]
                g[r0 + y][c0 + xb * 2] = byte & 0xF
                g[r0 + y][c0 + xb * 2 + 1] = byte >> 4
    return g


vals = {}
inkcols = [99, -1]
inkrows = [99, -1]
right_nonzero = 0
for i in range(min(3000, len(fb) // 128)):
    cell = fb[i * 128:(i + 1) * 128]
    for byte in cell:
        vals[byte & 0xF] = vals.get(byte & 0xF, 0) + 1
        vals[byte >> 4] = vals.get(byte >> 4, 0) + 1
    g = nibbles(cell)
    if any(any(r[c] for c in range(8, 16)) for r in g):
        right_nonzero += 1
    for y in range(16):
        for x in range(16):
            if g[y][x]:
                inkcols[0] = min(inkcols[0], x); inkcols[1] = max(inkcols[1], x)
                inkrows[0] = min(inkrows[0], y); inkrows[1] = max(inkrows[1], y)
print("  前 3000 字 nibble 值分布 = %s" % dict(sorted(vals.items())))
print("  墨迹列范围 = [%d, %d]   行范围 = [%d, %d]" % (inkcols[0], inkcols[1], inkrows[0], inkrows[1]))
print("  右半（列8..15）有非零的字数 = %d / 3000" % right_nonzero)

# 打印若干真实字形（找前 6 个非空字）
shown = 0
for i in range(len(fb) // 128):
    cell = fb[i * 128:(i + 1) * 128]
    if not any(cell):
        continue
    g = nibbles(cell)
    print("  --- gid %d (0x%04X) ---" % (i, i))
    for y in range(16):
        print("      " + "".join("#" if g[y][x] else "." for x in range(16)))
    shown += 1
    if shown >= 3:
        break

print()
print("=" * 78)
print("C. EWRAM 我方状态区可用量")
print("=" * 78)


def zerorun(buf, lo, hi):
    """返回 [lo,hi) 内最长连续零段 (start, end)"""
    best = (lo, lo)
    cur = None
    for a in range(lo, hi):
        if buf[a] == 0:
            if cur is None:
                cur = a
        else:
            if cur is not None and a - cur > best[1] - best[0]:
                best = (cur, a)
            cur = None
    if cur is not None and hi - cur > best[1] - best[0]:
        best = (cur, hi)
    return best


for tag in ("drive_org2", "drive_o_sum", "drive_o_menu", "drive_t_menu", "drive_o_party"):
    p = T / ("%s_ewram.bin" % tag)
    if not p.exists():
        continue
    buf = p.read_bytes()
    lo, hi = 0x0203FC00 - 0x02000000, 0x0203FFD2 - 0x02000000
    s, e = zerorun(buf, lo, hi)
    print("  %-14s 0x0203FC00..FFD2 最长零段 = 0x%08X..0x%08X (%d B)" % (tag, s + 0x02000000, e + 0x02000000, e - s))

rom = ROMF.read_bytes()
literals = set()
for i in range(0, len(rom) - 4):
    v = struct.unpack_from("<I", rom, i)[0]
    if 0x0203F000 <= v < 0x02040000:
        literals.add(v)
print("  全 ROM 里指向 0x0203F000..0x02040000 的 u32 字面量（%d 个）:" % len(literals))
for v in sorted(literals):
    print("      0x%08X" % v)
