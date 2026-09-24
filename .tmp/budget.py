# -*- coding: utf-8 -*-
"""VRAM 4 块预算表（判据级，不是采样求补集）。

依据（全部是**结构量**，不是「哪儿看起来空」）：
  1. BG 层的 tile **数据**寻址 = charBase*0x4000 + n*32，n ∈ [0,1024)（10 位号域）
     ⇒ 一个层的 tile 数据窗口 = 从它的 charBase 起的 **32KB = 2 个 charBlock**。
  2. 引擎字模缓存：0x08002950 设置 tileData(*0x03000328) 与 TB，
     预取器 0x080029E0 写 [tileData + TB*32, +512*32) = **512 砖 = 16KB**，
     font3 走 index*64 分支 ⇒ 一次装载占满 512 槽。TB 实测恒 1。
     它物理落在「该窗口的 n∈[TB, TB+512)」。
  3. tilemap：screenBase*0x800，与 charBase 无关（可以落在任何块）。每个 2KB = 64 砖。
  4. 静态美术：LZ77/RL 解压落点（原盘 dump 里非零但非缓存的部分）。

产出：逐页 × 逐块，列出 [tilemap / 引擎缓存 / 静态美术 / 自由] 的砖数，
并检验「把引擎缓存挪到邻块」这条提案**是否闭得住**。
"""
import glob, os, re, struct, sys

VR = 0x06000000
BLK = 0x4000
NB = 512          # 每块 512 砖（16KB / 32B）


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def load(tag, kind):
    p = ".tmp/drive_%s_%s.bin" % (tag, kind)
    return open(p, "rb").read() if os.path.exists(p) else None


def layers(io):
    """返回 [(bg, charBase, screenBase, enabled)]"""
    dispcnt = u16(io, 0)
    out = []
    for b in range(4):
        c = u16(io, 0x08 + 2 * b)
        out.append((b, (c >> 2) & 3, (c >> 8) & 0x1F, (dispcnt >> (8 + b)) & 1))
    return out


def tm_ranges(ls):
    """tilemap 占用的 (物理地址, 砖数) 列表 —— 每层 2KB = 64 砖"""
    out = []
    for bg, cb, sb, en in ls:
        addr = VR + sb * 0x800
        out.append((bg, sb, addr, 64))
    return out


def occupancy(vr, blk):
    """某块内非零砖的号集合"""
    base = blk * BLK
    nz = set()
    for n in range(NB):
        o = base + n * 32
        if vr[o:o + 32] != b"\x00" * 32:
            nz.add(n)
    return nz


def main():
    tags = sys.argv[1:] or ["o_title", "o_menu", "o_start", "o_bag", "o_party",
                            "o_sum", "o_info", "o_moves"]
    print("=" * 100)
    print("每页：BG0 = 文本层。列 = 各层的 (charBase, screenBase, 启用)")
    print("=" * 100)
    for t in tags:
        io, vr = load(t, "io"), load(t, "vram")
        if io is None or vr is None or len(vr) < 0x10000:
            print("%-8s  缺 dump" % t); continue
        ls = layers(io)
        cbs = sorted({cb for _, cb, _, en in ls if en})
        win = [(cb, cb + 1) for cb in cbs]
        print("\n%-8s BG0cb=%d  启用层 charBase=%s  窗口(块)=%s"
              % (t, ls[0][1], cbs, win))
        for bg, cb, sb, en in ls:
            print("      BG%d cb=%d sb=%-2d %s  tilemap=0x%08X"
                  % (bg, cb, sb, "ON " if en else "off", VR + sb * 0x800))
        # tilemap 占用按块归集
        tmo = {b: 0 for b in range(4)}
        for bg, sb, addr, n in tm_ranges(ls):
            blk = (addr - VR) // BLK
            if 0 <= blk < 4:
                tmo[blk] += n
        occ = {b: occupancy(vr, b) for b in range(4)}
        print("      %-6s %s" % ("块", "  ".join("cb%d" % b for b in range(4))))
        print("      %-6s %s" % ("非零砖", "  ".join("%3d" % len(occ[b]) for b in range(4))))
        print("      %-6s %s" % ("其中tilemap", "  ".join("%3d" % tmo[b] for b in range(4))))
        print("      %-6s %s" % ("自由砖", "  ".join("%3d" % (NB - len(occ[b])) for b in range(4))))
        # 提案检验：把某窗口的缓存挪到 n∈[512,1024) = 下一块
        for cb in cbs:
            nb = cb + 1
            if nb > 3:
                print("      ⇒ cb%d 的缓存无邻块可去（cb4 = OBJ 区）" % cb)
                continue
            free = NB - len(occ[nb])
            ok = "闭得住" if free >= 512 else "❌ 差 %d 砖" % (512 - free)
            print("      ⇒ cb%d 缓存挪到 cb%d：邻块自由 %3d 砖 / 需 512  → %s"
                  % (cb, nb, free, ok))


main()
