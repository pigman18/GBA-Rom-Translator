# -*- coding: utf-8 -*-
"""构建期静态判据：每个 tm1 模板的「我方池」物理区间 [td+0x4040, td+0x8000)
是否与 ① 自身 tilemap（screenblock）② 其余启用层 相交；并给容量。

BGxCNT 组合（0x08002878 实证）：CNT = tpl[3] | (tpl[2]<<8) | (tpl[1]<<2)
  bit2-3 = charBase   bit8-12 = screenBase   bit14-15 = size
"""
import struct

ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
d = open(ROM, "rb").read()
BASE, VRAM = 0x081BB3DC, 0x06000000
N, STRIDE = 53, 0x18
POOL_LO, POOL_HI = 514, 1024


def o(a):
    return a - 0x08000000


def sb_size(sz):
    return {0: 0x800, 1: 0x1000, 2: 0x1000, 3: 0x2000}[sz]


rows = []
for i in range(N):
    p = o(BASE + i * STRIDE)
    bg, cb, sb, p3 = d[p], d[p + 1], d[p + 2], d[p + 3]
    fo, tm = d[p + 8], d[p + 9]
    td = struct.unpack_from("<I", d, p + 0x0C)[0]
    mp = struct.unpack_from("<I", d, p + 0x10)[0]
    cnt = p3 | (sb << 8) | (cb << 2)
    size = (cnt >> 14) & 3
    sba = VRAM + ((cnt >> 8) & 0x1F) * 0x800
    rows.append(dict(i=i, bg=bg, cb=cb, fo=fo, tm=tm, td=td, mp=mp, size=size,
                     sba=sba, sb_end=sba + sb_size(size)))

print("== tm1 模板：我方池 vs 自身 tilemap ==")
bad = 0
for r in rows:
    if r["tm"] != 1:
        continue
    if r["cb"] >= 3:
        print("  idx%-3d cb=3  **池无处安放（分配器返回 0）**  td=%08X" % (r["i"], r["td"]))
        bad += 1
        continue
    lo = r["td"] + POOL_LO * 32
    hi = r["td"] + POOL_HI * 32
    ov = not (hi <= r["sba"] or lo >= r["sb_end"])
    tag = "⚠ 相交" if ov else "✓"
    print("  idx%-3d cb=%d td=%08X  池[%08X,%08X)  自身map[%08X,%08X)  %s"
          % (r["i"], r["cb"], r["td"], lo, hi, r["sba"], r["sb_end"], tag))
    if ov:
        bad += 1

print()
print("有问题条目:", bad)

print()
print("== 全部启用层在同一模板上的 screenblock 是否落进池区间（同 idx 内互查）==")
for r in rows:
    if r["tm"] != 1 or r["cb"] >= 3:
        continue
    lo = r["td"] + POOL_LO * 32
    hi = r["td"] + POOL_HI * 32
    for q in rows:
        if q["i"] == r["i"]:
            continue
        if not (q["sba"] < hi and q["sb_end"] > lo):
            continue
        print("  idx%-3d 池[%08X,%08X) 与 idx%-3d bg%d 的 map[%08X,%08X) 相交"
              % (r["i"], lo, hi, q["i"], q["bg"], q["sba"], q["sb_end"]))

print()
print("== 容量 ==")
print("  池 510 砖；12px 步进 ~3 砖/字 ⇒ 约 170 字/会话；8px 拉丁 2 砖/字 ⇒ 255 字")
