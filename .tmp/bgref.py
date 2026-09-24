# -*- coding: utf-8 -*-
"""bgref.py <tag_ours> [tag_orig] -- 「不撞 UI」判据（绝对地址口径）

为什么用绝对地址：
  map 项里的号 n 是**相对于该 BG 的 charBase** 的 tile index（0..1023），
  硬件地址 = 0x06000000 + charBase*0x4000 + n*32。
  我方写砖地址 = win.tileData + tileNo*32（tileNo 也是块内号，会自然溢出到下一块）。
  两侧换算成**绝对 VRAM 地址**后求交，就完全绕开「我算的是哪个块」的口径坑。

我方号段（v27，见 PrintNextChar_hook.c）：
  域 0 = CHS_OWN_BASE 352, 40 槽  -> addr = td + [352, 512)*32
  域 1 = CHS_FAR_BASE 656, 92 槽  -> addr = td + [656,1024)*32
  槽步进 CHS_SLOT_STRIDE = 4 tiles。

用法:  python .tmp/bgref.py t_title o_title
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
STRIDE = 4
OWN_BASE, OWN_N = 352, 40
FAR_BASE, FAR_N = 656, 92
TRACE, TR_TBL, TR_W, TR_N = 0x3C000, 8, 8, 24
VRAM_BASE = 0x06000000


def blob(tag, name):
    return (T / f"drive_{tag}_{name}.bin").read_bytes()


def io_cnt(io, i):
    return struct.unpack_from("<H", io, 0x08 + 2 * i)[0]


def our_domains(tag):
    """从 CHS_TRACE 窗口表读我方两个域的 (tileData, 号段, 地址区间)。

    窗口既可能在 IWRAM(0x03xxxxxx) 也可能在 EWRAM(0x0202xxxx)，两者都要收。
    v27 后域 1 用绝对块内号，不再依赖 tb ⇒ 只认 tileData 即可。
    """
    ewo = blob(tag, "ewram")
    tds = {}
    for i in range(TR_N):
        o = TRACE + (TR_TBL + i * TR_W) * 4
        w, tpl, td, mp, cnt = struct.unpack_from("<IIIII", ewo, o)
        ok = (0x02000000 <= w < 0x02040000) or (0x03000000 <= w < 0x03008000)
        if not ok or not td:
            continue
        tds[td] = tds.get(td, 0) + cnt
    doms = []
    for td in sorted(tds):
        doms.append((td, 0, OWN_BASE, td + OWN_BASE * 32,
                     td + (OWN_BASE + OWN_N * STRIDE) * 32))
        doms.append((td, 1, FAR_BASE, td + FAR_BASE * 32,
                     td + (FAR_BASE + FAR_N * STRIDE) * 32))
    return doms, tds


def report(our_tag, orig_tag=None):
    io, vram = blob(our_tag, "io"), blob(our_tag, "vram")
    disp = struct.unpack_from("<H", io, 0)[0]
    print("== ours[%s] DISPCNT=%04X   ours_vram=%d B" % (our_tag, disp, len(vram)))

    doms, tds = our_domains(our_tag)
    for td in sorted(tds):
        print("   窗口 tileData=%08X  (调用 %d 次)" % (td, tds[td]))
    for td, d, base, lo, hi in doms:
        print("   我方域%d tileData=%08X 号段=[%d,%d) 地址=[%08X,%08X)"
              % (d, td, base, base + (OWN_N if d == 0 else FAR_N) * STRIDE, lo, hi))

    # ---- 我方 ROM 运行时：谁被写到 UI 上？（直接看引擎 map 引用的砖） ----
    ui_hits = {}
    for i in range(4):
        cnt = io_cnt(io, i)
        if not (disp >> (8 + i)) & 1:
            print("   BG%d cnt=%04X (未使能)" % (i, cnt))
            continue
        cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
        w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
        off = sb * 0x800
        ref = {}
        for y in range(h):
            for x in range(w):
                e = struct.unpack_from("<H", vram, off + (y * w + x) * 2)[0]
                ref.setdefault(e & 0x3FF, []).append((x, y))
        high = sorted(n for n in ref if n >= 512)
        lowmax = max((n for n in ref if n < 512), default=None)
        nlow = len([n for n in ref if n < 512])
        print("   BG%d cnt=%04X charBase=%d(cb%d) screenBase=%d map=%dx%d"
              % (i, cnt, cb, cb, sb, w, h))
        print("      低号(字形缓存) %d 个 max=%s" % (nlow, lowmax))
        # UI = map 项 >= 512（落在 charBase+1 块）
        ui = {}
        for n in high:
            a = VRAM_BASE + cb * 0x4000 + n * 32
            ui[a] = n
        print("      ★ UI 号(>=512) %d 个 绝对块内偏移 %s"
              % (len(ui), sorted(n - 512 for n in ui.values())))
        for a in sorted(ui):
            for td, d, base, lo, hi in doms:
                if lo <= a < hi:
                    slot = (a - lo) // (STRIDE * 32)
                    print("      🔴 撞 UI：BG%d 号%d (addr %08X, cb%d内%d) 落在我方域%d 槽%d [%08X,%08X)"
                          % (i, ui[a], a, cb + 1, ui[a] - 512, d, slot, lo, hi))
        ui_hits[i] = ui

    # ---- 原盘参照：UI 图形占用哪些地址（原盘没有中文，>=512 必是框体美术） ----
    if orig_tag:
        oio, ovram = blob(orig_tag, "io"), blob(orig_tag, "vram")
        odisp = struct.unpack_from("<H", oio, 0)[0]
        print("== orig[%s] DISPCNT=%04X" % (orig_tag, odisp))
        oui = {}
        for i in range(4):
            cnt = io_cnt(oio, i)
            if not (odisp >> (8 + i)) & 1:
                continue
            cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
            w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
            off = sb * 0x800
            for y in range(h):
                for x in range(w):
                    e = struct.unpack_from("<H", ovram, off + (y * w + x) * 2)[0]
                    n = e & 0x3FF
                    if n >= 512:
                        a = VRAM_BASE + cb * 0x4000 + n * 32
                        oui[a] = (i, n)
        print("   原盘 UI 砖 %d 个，偏移范围 %s..%s (cb内偏移)"
              % (len(oui), min((n - 512) for _, n in oui.values()) if oui else "-",
                 max((n - 512) for _, n in oui.values()) if oui else "-"))
        bad = 0
        chg = 0
        for a in sorted(oui):
            i, n = oui[a]
            inours = any(lo <= a < hi for td, d, base, lo, hi in doms)
            off = a - VRAM_BASE
            content_changed = (off + 32 <= len(vram)
                               and vram[off:off + 32] != ovram[off:off + 32]
                               and any(ovram[off:off + 32]))
            if inours:
                bad += 1
                print("   🔴 号段撞：原盘 BG%d 号%d(addr %08X, cb内%d) 落我方域号段"
                      % (i, n, a, n - 512))
            elif content_changed:
                chg += 1
                print("   🟠 内容被改：原盘 BG%d 号%d(addr %08X) 砖内容变了 %s -> %s"
                      % (i, n, a, ovram[off:off + 8].hex(), vram[off:off + 8].hex()))
        print("   === 号段交集 %d 个 / 内容被改 %d 个 ===" % (bad, chg))
        return bad + chg
    return 0


if __name__ == "__main__":
    report(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
