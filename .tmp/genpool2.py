# -*- coding: utf-8 -*-
"""genpool2.py -- v35 段表生成器（直接输出可粘贴的 C 代码）。

相对 v34 的两处改动：
  ① 人口 0 从 69 槽缩到 54 槽（只留 [384,448) 32 槽 + [946,991) 22 槽）——
     实测需求峰值 17 槽，69 槽长期闲置。
  ② 人口 1 收编「cb2 可达范围内所有 >= 4 砖的空档」= 199 槽（v34 只有 167）。
     实测 t_info / t_moves 恰好把 167 槽用满 ⇒ LRU 淘汰把屏上已有的字挤掉。

归属原则（必须遵守，否则两域写同一物理砖）：
  · 物理砖只能有一个主人。人口 0 与人口 1 的可达范围**重叠于 cb2 低半**
    （p0 号 512..1023 / p1 号 0..511 指向同一批地址）⇒ 必须显式互斥。
  · 人口 0 优先拿 cb1 内唯一的大空档（别的域够不到）。
  · 其余全给人口 1（需求最大、且 cb0 窗口够不到 cb2）。

用法: python .tmp/genpool2.py
"""
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
VRAM_BASE = 0x06000000
BLK = 0x4000
TAGS = ["o_title", "o_menu", "o_bag", "o_party", "o_sum2", "o_info", "o_moves"]
MIN_TILES = 4          # 只收 >= 4 砖的空档（=2 槽），免得段表被 1 槽碎片撑爆

DOM_BASE = {0: 0x06004000, 1: 0x06008000, 2: 0x06000000}
DOM_RANGE = {0: (0x06004000, 0x0600C000),
             1: (0x06008000, 0x06010000),
             2: (0x06000000, 0x06008000)}
# 人工钉死：人口 0 的两段（cb1 大空档 + cb2 高段 [946,991)）
PIN0 = [(0x06007000, 0x06007800), (0x0600B640, 0x0600BBE0)]


def used():
    s = set()
    for tag in TAGS:
        f_io, f_vr = T / f"drive_{tag}_io.bin", T / f"drive_{tag}_vram.bin"
        if not (f_io.exists() and f_vr.exists()):
            continue
        io, vram = f_io.read_bytes(), f_vr.read_bytes()
        disp = struct.unpack_from("<H", io, 0)[0]
        for i in range(4):
            cnt = struct.unpack_from("<H", io, 0x08 + 2 * i)[0]
            if not (disp >> (8 + i)) & 1:
                continue
            cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
            w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
            off = sb * 0x800
            for b in range(off, off + w * h * 2, 32):
                s.add(VRAM_BASE + b)
            for y in range(h):
                for x in range(w):
                    e = struct.unpack_from("<H", vram, off + (y * w + x) * 2)[0]
                    s.add(VRAM_BASE + cb * BLK + (e & 0x3FF) * 32)
    return s


def free_runs(s, lo, hi, skip=()):
    out, a = [], lo
    while a < hi:
        if a in s or any(s0 <= a < e0 for s0, e0 in skip):
            a += 32
            continue
        b = a
        while b < hi and b not in s and not any(s0 <= b < e0 for s0, e0 in skip):
            b += 32
        if (b - a) // 32 >= MIN_TILES:
            out.append((a, b))
        a = b
    return out


def emit(dom, runs):
    base = DOM_BASE[dom]
    segs = [(r0 - base) // 32 for r0, _ in runs]
    sl = [(b - a) // 32 // 2 for a, b in runs]
    tot = sum(sl)
    print("/* 人口 %d: %d 槽 (%d 段) */" % (dom, tot, len(segs)))
    print("static const uint16_t chs_p%d_seg_b[%d] = { %s };"
          % (dom, len(segs), ", ".join("%du" % b for b in segs)))
    print("static const uint8_t  chs_p%d_seg_n[%d] = { %s };"
          % (dom, len(sl), ", ".join("%du" % k for k in sl)))
    # 静态断言（故意把段表数字再写一遍，好和槽数宏互相校验；只放得下 6 段的宏
    # 会超长，故 >8 段时按 6 个一行折行）
    macro = {0: "CHS_OWN_SLOT_N", 1: "CHS_FAR_SLOT_N", 2: "CHS_CB0_SLOT_N"}[dom]
    terms = [("%du" % k) for k in sl]
    lines = ["+ ".join(terms[i:i + 6]) for i in range(0, len(terms), 6)]
    body = ("\n               + ".join(lines))
    print('_Static_assert(( %s ) == %s, "p%d seg sum != %s");'
          % (body, macro, dom, macro))
    print('_Static_assert(sizeof(chs_p%d_seg_b) / sizeof(chs_p%d_seg_b[0]) == %du,'
          ' "p%d seg count");' % (dom, dom, len(segs), dom))
    # 校验：号域不得越 1023
    for b, k in zip(segs, sl):
        if b + k * 2 > 1024:
            print("!! 人口 %d 段 %d 越界: 号 %d" % (dom, b, b + k * 2))
    return tot, len(segs), segs, sl


def main():
    s = used()
    print("/* 引擎已用砖 %d 个 (原盘 %d 页并集), MIN_TILES=%d */"
          % (len(s), len(TAGS), MIN_TILES))
    tot0, n0, b0, k0 = emit(0, [r for r in free_runs(s, *DOM_RANGE[0]) if r in PIN0
                                or any(a <= r[0] and r[1] <= b for a, b in PIN0)])
    r1 = free_runs(s, *DOM_RANGE[1], skip=PIN0)
    tot1, n1, b1, k1 = emit(1, r1)
    tot2, n2, b2, k2 = emit(2, [r for r in free_runs(s, 0x06001800, 0x06003000)])

    # 互斥校验：两域物理地址不得相交
    import itertools
    def addr(dom, segs, sl):
        out = set()
        for b, k in zip(segs, sl):
            for i in range(k * 2):
                out.add(DOM_BASE[dom] + (b + i) * 32)
        return out
    a0, a1, a2 = addr(0, b0, k0), addr(1, b1, k1), addr(2, b2, k2)
    print("/* 物理重叠: p0&p1=%d p0&p2=%d p1&p2=%d */"
          % (len(a0 & a1), len(a0 & a2), len(a1 & a2)))
    print("/* 槽数: OWN(p0)=%d FAR(p1)=%d CB0(p2)=%d ；KEYS_MAX 需 >= %d */"
          % (tot0, tot1, tot2, max(tot0, tot1, tot2)))
    # 槽表偏移
    off, cur = {}, 0x8B0
    for name, n in (("KEYS0", tot0), ("STAMPS0", tot0), ("KEYS1", tot1),
                    ("STAMPS1", tot1), ("KEYS2", tot2), ("STAMPS2", tot2)):
        off[name] = cur
        cur += n * (8 if name.startswith("KEYS") else 4)
        cur = (cur + 0xF) & ~0xF          # 16 字节对齐，留肉眼可辨的空隙
    for name, n in (("KEYS0", tot0), ("STAMPS0", tot0), ("KEYS1", tot1),
                    ("STAMPS1", tot1), ("KEYS2", tot2), ("STAMPS2", tot2)):
        print("#define CHS_SLAB_%-8s 0x%08Xu   /* %d x %d */"
              % (name, off[name], n, 8 if name.startswith("KEYS") else 4))
    print("/* 表尾 0x%X ＜ 游戏数据区 0x1FD2 */" % cur)


if __name__ == "__main__":
    main()
