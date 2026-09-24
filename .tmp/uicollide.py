# -*- coding: utf-8 -*-
"""uicollide.py <tag> [tag_orig] -- 逐 BG 核对「我们的图集 vs 屏幕真正引用的号」

判据（用户裁定的唯一正确判据）：**tilemap 是否引用该号**。
对每个开启的 BG 层：
  1. 由 BGxCNT 读出 charBase / screenBase / size，展开整张 map，收集被引用的号；
  2. 从 slab 求出我方两域各槽占用的号；
  3. 报告：
     · 我方号里**被屏幕引用**的（= 屏上能看到的字）
     · 被我方占用但 **map 引用的不是我方 slab** 的号（= 撞 UI：那块砖本来是美术）
  4. 若给了 tag_orig（原盘同一页 dump），再逐砖比 VRAM，列出「我方改过且屏幕仍在引用」
     的号 —— 这些就是实锤的撞 UI 现场。

用法:  python .tmp/uicollide.py t_menu o_menu
       需要 .tmp/drive_<tag>_{vram,ewram,iwram}.bin 与 IO 打印（见 tr_run.py）
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")

STRIDE, OWN_BASE, OWN_N = 4, 352, 40
FAR_BASE, FAR_N = 528, 92
KEYS0, KEYS1, SLAB = 0x08, 0x458, 0x3E000
TRACE, TR_TBL, TR_W, TR_N = 0x3C000, 8, 8, 24


def vram_of(tag):
    return (T / ("drive_%s_vram.bin" % tag)).read_bytes()


def ewram_of(tag):
    return (T / ("drive_%s_ewram.bin" % tag)).read_bytes()


def iwram_of(tag):
    return (T / ("drive_%s_iwram.bin" % tag)).read_bytes()


def domains(tag):
    """从 diag 窗口表求 (dom -> (tileData, tb, win))。"""
    ew, iw = ewram_of(tag), iwram_of(tag)
    out = {}
    for i in range(TR_N):
        o = TRACE + (TR_TBL + i * TR_W) * 4
        w, tpl, td, mp, cnt = struct.unpack_from("<IIIII", ew, o)
        if not w or not td:
            continue
        dom = 0 if (((td & 0xFFFFC000) + 0x4000) in (0x06004000, 0x06008000)) else 1
        tb = iw[w - 0x03000000 + 0x16]
        out[dom] = (td, tb, w, cnt)
    return out


def slab_tiles(ew, dom):
    ko, n = (KEYS1, FAR_N) if dom else (KEYS0, OWN_N)
    used = {}
    for i in range(n):
        lo = struct.unpack_from("<I", ew, SLAB + ko + i * 8)[0]
        if lo:
            used[lo] = i
    return used


def main(tag, tag_orig=None):
    vw = vram_of(tag)
    ew = ewram_of(tag)
    dm = domains(tag)
    print("== %s 我方域" % tag)
    for d in sorted(dm):
        td, tb, w, cnt = dm[d]
        base = (FAR_BASE + tb) if d else OWN_BASE
        n = FAR_N if d else OWN_N
        print("   域%d tileData=%08X tb=%d win=%08X 落字数=%d  号域=[%d,%d)"
              % (d, td, tb, w, cnt, base, base + n * STRIDE))
        # 我方两域在**全局号**上的位置（map 存的是全局号）
        print("      槽内容: " + " ".join(
            "%d:%04X" % (i, struct.unpack_from("<I", ew, SLAB + (KEYS1 if d else KEYS0) + i * 8)[0])
            for i in range(min(n, 6))))

    # 全局号 ←→ 地址：VRAM 偏移 = 号 * 32（map 里的号是全局 tile index）
    def tile_bytes(n):
        o = n * 32
        return vw[o:o + 32]

    # 我方 slab 在**全局号**空间下实际落在哪：td + 号*32 ⇒ 全局号 = (td-0x06000000)/32 + 号
    glob = {}
    for d in sorted(dm):
        td, tb, w, cnt = dm[d]
        base = (FAR_BASE + tb) if d else OWN_BASE
        n = FAR_N if d else OWN_N
        for i in range(n):
            lo = struct.unpack_from("<I", ew, SLAB + (KEYS1 if d else KEYS0) + i * 8)[0]
            if not lo:
                continue
            b = base + i * STRIDE
            glob[(td - 0x06000000) // 32 + b] = (d, i, lo, td + b * 32)
    print("   我方占用全局号 %d 个，范围 %s"
          % (len(glob), sorted(glob)[:4] + ["..."] + sorted(glob)[-2:]
             if glob else "无"))

    # 逐 BG 展开 map
    ref = {}          # 号 -> 引用的 BG 列表
    for i in range(4):
        cnt = int(sys.argv[3 + i], 16) if len(sys.argv) > 3 + i else None
        if cnt is None:
            break
        if not (cnt & 0x80):        # bit7 = 不透明/使能（BG0 的 bit7 是 mosaic；用 priority 判不了）
            enabled = True if i else True
        cb = (cnt >> 2) & 3
        sb = (cnt >> 8) & 0x1F
        size = (cnt >> 14) & 3
        dims = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
        off = sb * 0x800
        print("   BG%d cnt=%04X charBase=%d screenBase=%d size=%d map=%dx%d @0x06%05X"
              % (i, cnt, cb, sb, size, dims[0], dims[1], off))
        for y in range(dims[1]):
            for x in range(dims[0]):
                e = struct.unpack_from("<H", vw, off + (y * dims[0] + x) * 2)[0]
                n = e & 0x3FF
                ref.setdefault(n, []).append((i, x, y))
    # 只统计前 20 行（可见区）
    vis = {n: v for n, v in ref.items() if any(y < 20 for _, _, y in v)}
    print("   可见区被引用的号 %d 个，范围 [%d, %d]"
          % (len(vis), min(vis), max(vis)) if vis else "   可见区无引用")
    hit = sorted(set(vis) & set(glob))
    print("   ★ 我方号被屏幕引用: %d 个 %s" % (len(hit), hit[:24]))
    miss = sorted(n for n in hit if len(vis[n]) == 0)
    # 我方号里**没被引用**的（浪费/陈旧）
    idle = sorted(set(glob) - set(vis))
    print("   · 我方号未被引用（陈旧/浪费）: %d 个" % len(idle))

    # 关键：屏幕引用的号里，落在「我方域地址区间」但 map 号不等于我方号的
    for d in sorted(dm):
        td, tb, w, cnt = dm[d]
        lo_n = (td - 0x06000000) // 32
        hi_n = lo_n + 1024
        inside = sorted(n for n in vis if lo_n <= n < hi_n)
        ours = set(glob)
        bad = [n for n in inside if n not in ours]
        print("   域%d 全局号区间 [%d,%d)：屏幕引用 %d 个，其中**不是我方槽** %d 个 %s"
              % (d, lo_n, hi_n, len(inside), len(bad), bad[:24]))
        if bad:
            for n in bad[:12]:
                print("       号 %d 被 %s 引用 | 本砖前 16B = %s"
                      % (n, vis[n][:3], tile_bytes(n)[:16].hex()))
            if tag_orig:
                vo = vram_of(tag_orig)
                diff = [n for n in bad if vo[n * 32:n * 32 + 32] != tile_bytes(n)]
                print("       ★★ 与**原盘**逐砖不同的: %d 个 %s"
                      % (len(diff), diff[:24]))
                for n in diff[:8]:
                    print("          号 %d 我方=%s" % (n, tile_bytes(n)[:16].hex()))
                    print("               原盘=%s" % vo[n * 32:n * 32 + 16].hex())
    # 原盘对照（全 VRAM 差异块统计）
    if tag_orig:
        vo = vram_of(tag_orig)
        by_blk = {}
        for o in range(0, 0x18000, 32):
            if vo[o:o + 32] != vw[o:o + 32]:
                by_blk.setdefault(o // 0x4000, []).append(o // 32)
        print("   == 与原盘逐砖差异（按 charBlock）==")
        for b in sorted(by_blk):
            ns = by_blk[b]
            print("     cb%d: %d 砖  %s" % (b, len(ns), ns[:20]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("0x") else None)
