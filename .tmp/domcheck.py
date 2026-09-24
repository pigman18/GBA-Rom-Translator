# -*- coding: utf-8 -*-
"""每个采样页：引擎字模缓存的「活动模板」+ 该页用到的域（tileData）。
判据：引擎预取写 tileData + [TB*32, TB*32+16384)（16 KB = 整块）。
若某域的池子落进 [TB*32, TB*32+16384)，就会被引擎周期性抹掉。"""
import glob, os, struct, sys

ROM = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
B = 0x08000000
rom = open(ROM, "rb").read()

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]

# 池子（源码现状 v36）
POOLS = {1: [(384, 32), (946, 22)], 2: [(514, 127)], 0: [(192, 32), (320, 32)]}
CBASE = {0: 0x06000000, 1: 0x06004000, 2: 0x06008000}

print("=" * 96)
print("A. 各页「活动模板」(*0x03000328) 与字模写入区间")
print("=" * 96)
print("%-10s %-11s %-8s %-4s %-4s %-4s %-9s %s" %
      ("page", "tplPtr", "tileData", "TB", "cnt", "f8", "N", "字模写入区 [  ,  )"))
print("-" * 96)
active = {}
for p in sorted(glob.glob(".tmp/drive_*_iwram.bin")):
    tag = os.path.basename(p)[6:-10]
    b = open(p, "rb").read()
    if len(b) < 0x340:
        continue
    tp, tb, ct = u32(b, 0x328), u16(b, 0x32C), u16(b, 0x32E)
    if not (0x08000000 <= tp < 0x0A000000):
        print("%-10s (tpl=0x%08X 非 ROM 指针)" % (tag, tp))
        continue
    o = tp - B
    f8 = rom[o + 8]
    td = struct.unpack_from("<I", rom, o + 0x0C)[0]
    N = 512 if f8 in (0, 3) else 256
    lo, hi = td + tb * 32, td + tb * 32 + N * 32
    active[tag] = (td, tb, N, lo, hi)
    print("%-10s 0x%08X 0x%08X %-4d %-4d %-4d %-4d 0x%08X..0x%08X  (%d KB 块 %d)" %
          (tag, tp, td, tb, ct, f8, N, lo, hi, N * 32 // 1024,
           (td - 0x06000000) // 0x4000 if td >= 0x06000000 else -1))

print()
print("=" * 96)
print("B. 该页用到的「域」（来自 CHS_TRACE 窗口表 tileData）")
print("=" * 96)
TR = 0x3C000
print("%-10s %-28s %-24s %s" % ("page", "域(tileData):窗口数", "动态TB@0x0202E6EE", "字模区(按A)"))
print("-" * 96)
for p in sorted(glob.glob(".tmp/drive_*_ewram.bin")):
    tag = os.path.basename(p)[6:-10]
    ew = open(p, "rb").read()
    if len(ew) < TR + 0x400:
        continue
    magic = u32(ew, TR)
    doms = {}
    if magic == 0x32584441:
        for i in range(24):
            o = TR + 0x20 + i * 32
            td = u32(ew, o + 8); cnt = u32(ew, o + 16)
            if td and cnt:
                doms[td] = doms.get(td, 0) + cnt
    dyn = u16(ew, 0x2E6EE)
    a = active.get(tag)
    print("%-10s %-28s 0x%04X (%-5d)      %s" % (
        tag,
        " ".join("0x%08X:%d" % (k, v) for k, v in sorted(doms.items())) or "-",
        dyn, dyn,
        ("0x%08X..0x%08X" % (a[3], a[4])) if a else "-"))

print()
print("=" * 96)
print("C. 池子 vs 字模区 重叠核算（用 A 里各页实测的字模区）")
print("=" * 96)
print("池子定义：人口0(cb1) 384/+32  946/+22 | 人口1(cb2) 514/+127 | 人口2(cb0) 192/+32 320/+32")
for tag, (td, tb, N, lo, hi) in sorted(active.items()):
    dom = (td - 0x06000000) // 0x4000
    print("\n  %-10s 字模区 = 0x%08X..0x%08X   (活动域 = 人口 %d)" % (tag, lo, hi, dom))
    for d in (0, 1, 2):
        segs = POOLS[d]
        base = CBASE[d]
        dirty = []
        for (b0, n) in segs:
            s, e = base + b0 * 32, base + b0 * 32 + n * 64   # 1 槽 = 2 砖 = 64 B
            if s < hi and e > lo:
                ov = min(e, hi) - max(s, lo)
                dirty.append("号%d..%d(0x%08X..0x%08X 重叠 %dB)" % (b0, b0 + n * 2, s, e, ov))
        mark = "   ← 危险" if dirty else ""
        print("     人口 %d: %-2d 槽  %s%s" % (d, sum(n for _, n in segs),
                                             "; ".join(dirty) if dirty else "不重叠", mark))
