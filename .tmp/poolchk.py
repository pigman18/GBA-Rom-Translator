# -*- coding: utf-8 -*-
"""poolchk.py [preset] -- 号池「物理地址是否踩到引擎自己的东西」检查器。

判据基准取**原盘 dump（o_*）**：同一屏面的静态美术/地图表在改版里位置不变，
所以「原盘某 BG 的 map 引用了一个落在号池里的绝对地址」= 真冲突。

硬件口径：map 项 n 的地址 = 0x06000000 + charBase*0x4000 + n*32。
另查：任一使能 BG 的 tilemap 字节区间与号池区间相交（我们写砖会改坏地图表）。

用法: python .tmp/poolchk.py [v32|v33|...]
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
VRAM_BASE = 0x06000000
CHAR_BLK = 0x06008000
STRIDE = 4

# (起始 canonical 号, 槽数)，槽步进 4
PRESETS = {
    "v32": [(384, 32), (540, 15), (612, 39), (960, 16)],
    "v33": [(384, 24), (256, 32), (540, 15), (612, 39), (912, 24)],
}
ORIG_TAGS = ["o_title", "o_menu", "o_bag", "o_party", "o_sum2", "o_info", "o_moves"]


def blob(tag, name):
    p = T / f"drive_{tag}_{name}.bin"
    return p.read_bytes() if p.exists() else None


def ranges(preset):
    return [(base, n, CHAR_BLK + base * 32, CHAR_BLK + (base + n * STRIDE) * 32)
            for base, n in PRESETS[preset]]


def merge(addrs):
    """把地址列表并成区间。"""
    addrs = sorted(addrs)
    out = []
    for a in addrs:
        if out and a == out[-1][1]:
            out[-1][1] = a + 32
        else:
            out.append([a, a + 32])
    return [(lo, hi) for lo, hi in out]


def check(tag, pool):
    io, vram = blob(tag, "io"), blob(tag, "vram")
    if io is None or vram is None:
        return [], []
    disp = struct.unpack_from("<H", io, 0)[0]
    map_hits, ref_hits = [], []
    for i in range(4):
        cnt = struct.unpack_from("<H", io, 0x08 + 2 * i)[0]
        if not (disp >> (8 + i)) & 1:
            continue
        cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
        w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
        off = sb * 0x800
        mlo, mhi = VRAM_BASE + off, VRAM_BASE + off + w * h * 2
        for base, n, lo, hi in pool:
            if lo < mhi and mlo < hi:
                map_hits.append((i, base, mlo, mhi, lo, hi))
        for y in range(h):
            for x in range(w):
                e = struct.unpack_from("<H", vram, off + (y * w + x) * 2)[0]
                a = VRAM_BASE + cb * 0x4000 + (e & 0x3FF) * 32
                for base, n, lo, hi in pool:
                    if lo <= a < hi:
                        ref_hits.append((i, cb, e & 0x3FF, a, base, x, y))
    return map_hits, ref_hits


def main():
    preset = sys.argv[1] if len(sys.argv) > 1 else "v33"
    pool = ranges(preset)
    print("== preset %s ==" % preset)
    for base, n, lo, hi in pool:
        print("   段 base=%4d n=%2d 号[%4d,%4d) addr[%08X,%08X) %4d B"
              % (base, n, base, base + n * STRIDE, lo, hi, hi - lo))
    total = 0
    for tag in ORIG_TAGS:
        mh, rh = check(tag, pool)
        if not mh and not rh:
            continue
        print("-- %s  (原盘基准)" % tag)
        for i, base, mlo, mhi, lo, hi in mh:
            print("   ⛔ 地图表相交: BG%d tilemap[%08X,%08X) vs 池段base=%d[%08X,%08X)"
                  % (i, mlo, mhi, base, lo, hi))
            total += 1
        for lo, hi in merge([a for _, _, _, a, _, _, _ in rh]):
            grp = [r for r in rh if lo <= r[3] < hi]
            print("   ⛔ 砖被引用: [%08X,%08X) %d 砖  BG%d cb%d 号%d..%d 池段base=%d"
                  % (lo, hi, (hi - lo) // 32, grp[0][0], grp[0][1],
                     grp[0][2], grp[-1][2], grp[0][4]))
            total += 1
    print("=== 冲突合计 %d ===" % total)


if __name__ == "__main__":
    main()
