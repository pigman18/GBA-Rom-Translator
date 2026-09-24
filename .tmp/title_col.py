# -*- coding: utf-8 -*-
"""title_col.py -- 标题菜单「我们 vs 原盘」的号引用对照。

判据：**原盘** BG0 的 tilemap 引用了哪些号；这些号里有多少落在**我方槽域**。
落在里面的 = 屏幕要用的美术砖，被我们的字形图集盖掉了 = 撞 UI 现场。

用法:  python .tmp/title_col.py t_title o_title 31 2
       (tag_ours tag_orig screenBase charBase)
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
STRIDE, OWN_BASE, OWN_N = 4, 352, 40
FAR_BASE, FAR_N = 528, 92
KEYS0, KEYS1, SLAB = 0x08, 0x458, 0x3E000
TRACE, TR_TBL, TR_W, TR_N = 0x3C000, 8, 8, 24

ours_tag, orig_tag = sys.argv[1], sys.argv[2]
SB = int(sys.argv[3])
CB = int(sys.argv[4]) if len(sys.argv) > 4 else 2
HOFS = int(sys.argv[5], 16) if len(sys.argv) > 5 else 0


def load(tag):
    return {
        "vram": (T / f"drive_{tag}_vram.bin").read_bytes(),
        "ewram": (T / f"drive_{tag}_ewram.bin").read_bytes(),
        "iwram": (T / f"drive_{tag}_iwram.bin").read_bytes(),
    }


O, R = load(ours_tag), load(orig_tag)


def maps(blob):
    """返回 (号 -> [(map_x, map_y, 屏幕内?)])。map 32x32 @ screenBase。"""
    off = SB * 0x800
    hx = (HOFS // 8) & 31
    hy = (HOFS // 8) & 31
    out = {}
    for y in range(32):
        for x in range(32):
            e = struct.unpack_from("<H", blob["vram"], off + (y * 32 + x) * 2)[0]
            n = e & 0x3FF
            vis = ((x - hx) & 31) < 30 and ((y - hy) & 31) < 20
            out.setdefault(n, []).append((x, y, vis, e >> 12))
    return out


def slotnums(blob):
    """我方两域占用的 map 号（= 块内号）。"""
    ew, iw = blob["ewram"], blob["iwram"]
    res = {}
    for i in range(TR_N):
        o = TRACE + (TR_TBL + i * TR_W) * 4
        w, tpl, td, mp, cnt = struct.unpack_from("<IIIII", ew, o)
        if not (0x03000000 <= w < 0x03008000) or not td:
            continue
        cb = (td - 0x06000000) // 0x4000
        dom = 0 if (((td & 0xFFFFC000) + 0x4000) in (0x06004000, 0x06008000)) else 1
        tb = iw[w - 0x03000000 + 0x16]
        base = (FAR_BASE + tb) if dom else OWN_BASE
        n = FAR_N if dom else OWN_N
        keys = KEYS1 if dom else KEYS0
        live = [i2 for i2 in range(n)
                if struct.unpack_from("<I", ew, SLAB + keys + i2 * 8)[0]]
        res[dom] = dict(cb=cb, tb=tb, base=base, n=n, live=live, win=w, td=td)
    return res


mo, mr = maps(O), maps(R)
so = slotnums(O)

print("== 我方窗口域 ==")
for d in sorted(so):
    v = so[d]
    nums = [v["base"] + i * STRIDE for i in v["live"]]
    print("  域%d tileData=%08X (cb%d) tb=%d 号段=[%d,%d) 在用槽=%d 号范围=%s"
          % (d, v["td"], v["cb"], v["tb"], v["base"], v["base"] + v["n"] * STRIDE,
             len(v["live"]), (min(nums), max(nums)) if nums else None))

# 我方号段所在的 charBlock（map 号 512 以上 = 下一个 charBlock）
for d in sorted(so):
    v = so[d]
    lo, hi = v["base"], v["base"] + v["n"] * STRIDE
    print("  域%d 号段 [%d,%d) 落在 charBlock %d (号//512)"
          % (d, lo, hi, lo // 512))

ref_o = set(n for n, l in mo.items() if any(x[2] for x in l))
ref_r = set(n for n, l in mr.items() if any(x[2] for x in l))
print("\n== 可见区被引用的号 ==")
print("  我方 ROM: %d 个" % len(ref_o))
print("  原盘    : %d 个, 范围 [%d,%d]" % (len(ref_r), min(ref_r), max(ref_r)))
print("  原盘 引用 ∩ [352,512) : %s" % sorted(n for n in ref_r if 352 <= n < 512))
print("  原盘 引用 ∩ [512,1024): %s" % sorted(n for n in ref_r if n >= 512))
print("  我方 引用 ∩ [352,512) : %s" % sorted(n for n in ref_o if 352 <= n < 512))
print("  我方 引用 ∩ [512,1024): %s" % sorted(n for n in ref_o if n >= 512))

# ★ 核心判据：原盘 map 引用的号里，我方 VRAM 与原盘**逐砖不同**的 = 被我方毁掉的美术
# ★ 号 → VRAM 偏移：map 号 N 落在 charBase 块内 ⇒ 地址 = charBase*0x4000 + N*32
#   （N>=512 时自然跨到下一个 charBlock，与前缀一致）
def adr(n):
    return CB * 0x4000 + n * 32


print("\n== ★ 原盘引用的号里，被我们改写了砖内容的 ==")
dmg = []
for n in sorted(ref_r):
    a = O["vram"][adr(n):adr(n) + 32]
    b = R["vram"][adr(n):adr(n) + 32]
    if a != b:
        dmg.append(n)
print("   共 %d 个: %s" % (len(dmg), dmg))
for n in dmg[:20]:
    print("      号%-4d 原盘=%s" % (n, R["vram"][adr(n):adr(n) + 16].hex()))
    print("             我方=%s" % O["vram"][adr(n):adr(n) + 16].hex())

# 反方向：我们把哪些**没被引用**的号也改了（无害，但说明占用范围）
print("\n== 我方改动过、且原盘 map 没引用的号（无害占用）==")
ch = [n for n in range(1024)
      if O["vram"][adr(n):adr(n) + 32] != R["vram"][adr(n):adr(n) + 32]]
print("   我方共改了 %d 砖；其中原盘引用到的 = %d"
      % (len(ch), len([n for n in ch if n in ref_r])))
if ch:
    print("   改动号范围 [%d,%d]" % (min(ch), max(ch)))
    print("   改动号按 512 分段: <512 = %d 个, >=512 = %d 个"
          % (len([n for n in ch if n < 512]), len([n for n in ch if n >= 512])))
print("\n== 双方都引用的号（= 争用现场）==")
print("   %s" % sorted(ref_r & ref_o))
print("\n== 原盘引用号全集 ==")
print("   %s" % sorted(ref_r))
print("   (去掉 <250 的日文字形缓存后) %s"
      % sorted(n for n in ref_r if n >= 250))
print("\n== 我方引用号全集 ==")
print("   %s" % sorted(ref_o))
