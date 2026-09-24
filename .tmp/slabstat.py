# -*- coding: utf-8 -*-
"""slabstat.py <tag> -- 读 CHS_SLAB 槽表，看用了多少槽 / 有无淘汰。

用法: python .tmp/slabstat.py t_moves
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
SLAB = 0x3E000          # 0x0203E000 - 0x02000000
# v33：三张表（人口 = 窗口所在 BG 层的 charBase），偏移必须与 C 侧同步。
KEYS, STAMPS = 0x1A0, 0x430        # 兼容旧名
TABLES = [(0, 0x008, 0x118, 34), (1, 0x1A0, 0x430, 82), (2, 0x578, 0x678, 32)]
MAGIC = 0x4232544C


def u32(e, o):
    return struct.unpack_from("<I", e, SLAB + o)[0]


def main(tag):
    e = (T / f"drive_{tag}_ewram.bin").read_bytes()
    print("%s magic=%08X tick=%d" % (tag, u32(e, 0), u32(e, 4)))
    if u32(e, 0) != MAGIC:
        print("  (magic 不符 —— 表可能未建立)")
    for dom, ko, so, n in TABLES:
        used = []
        zero = 0
        for i in range(n):
            lo = u32(e, ko + i * 8)
            hi = u32(e, ko + i * 8 + 4)
            st = u32(e, so + i * 4)
            if lo == 0 and hi == 0:
                zero += 1
                continue
            used.append((i, lo, hi, st))
        print("  域%d: 非空 %d / %d  空槽 %d" % (dom, len(used), n, zero))
        if used:
            sts = sorted(x[3] for x in used)
            print("     时间戳 min=%d max=%d 中位=%d" % (sts[0], sts[-1], sts[len(sts) // 2]))
            # lo = (key<<3)|phase, key = (code<<8)|(lib<<4)|ink  => code = lo>>11
            codes = sorted(x[1] >> 11 for x in used)
            print("     不同字符码 %d 个: %s" % (len(set(codes)), [hex(c) for c in sorted(set(codes))]))
            dup = len(used) - len(set((x[1], x[2]) for x in used))
            print("     重复键 %d" % dup)


if __name__ == "__main__":
    main(sys.argv[1])
