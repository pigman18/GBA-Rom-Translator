# -*- coding: utf-8 -*-
"""tpl_x_page.py — 「窗口模板 × 页面」静态交叉表（本轮核心）。

为什么必须做这一步：
  `tpl_capacity.py` 用**全体页面资产的并集**求补集 ⇒ cb1 显示「空闲 0 砖」。
  那算法把「图鉴页的图集」算成「对话框页被占」，是上一轮已自认的错误。
  真实关系是：**每条模板只被若干特定函数（界面）引用**，只需扣**那些函数**加载的美术。

判据链（全部逐指令实证，见 docs/调研_20260921d）：
  · 定号公式 0x08002D1C：  dst = tpl->tileData + (win[0x16] + win[0x18]) * 32
  · 引擎字模缓存（单例）： 0x08002950 配置 tileBase≡1 ；0x080029E0 写 tileData + [1,513)
    ⇒ 同一时刻只有**一个**块被预取写。我方要占的是**该块的下一块**的号 [1,512)。

本脚本输出：
  A. 每条模板的引用点 + 回溯到的函数入口（= 使用该模板的界面）
  B. 对每条模板：其「下一块」被**它的使用者**里的函数占了多少砖（取并集）
     —— 这才是该模板真实的可用槽数（不是全体页面的并集）
"""
from __future__ import annotations

import os
import re
import struct
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000
VRAM = 0x06000000
TPL_LO, TPL_HI, TPL_STEP = 0x081BB3DC, 0x081BB8BC, 0x18


def u16(rom, a):
    return struct.unpack_from("<H", rom, a - BASE)[0]


def is_prologue(rom, a):
    return (u16(rom, a) & 0xFF00) == 0xB500


def is_end(rom, a):
    hw = u16(rom, a)
    if (hw & 0xFF87) == 0x4700:
        return True
    if (hw & 0xF800) == 0xE000:
        return ((hw >> 8) & 0xF) in (0xE, 0xF, 0x1, 0xD)
    if (hw & 0xFE00) == 0xBC00:
        return True
    return False


def owner(rom, site, lim=0x400):
    """从 site 向上回溯找函数入口（push {...,lr} + 前一条是边界）。"""
    a = site - 2
    end = site - lim
    while a > end:
        if is_prologue(rom, a):
            if is_end(rom, a - 2) or a == site - 2 or u16(rom, a - 2) == 0x0000:
                return a
        a -= 2
    return None


def scan_refs(rom, lo, hi):
    """返回 {模板地址: [引用点ROM地址,...]}（4 字节 LE 常量，落在模板表内）。"""
    refs = defaultdict(list)
    for off in range(0, len(rom) - 4, 2):          # 2 字节对齐扫（Thumb 常量池 4 对齐，宽一点无妨）
        v = struct.unpack_from("<I", rom, off)[0]
        if lo <= v < hi:
            refs[v].append(BASE + off)
    return refs


def load_page_blocks():
    """从 .tmp/lz_own_all.txt 解析 {函数地址: [(dst, tiles)]}，只保留写 BG VRAM 的。"""
    pages = defaultdict(list)
    site = "?"
    p = os.path.join(ROOT, ".tmp", "lz_own_all.txt")
    for ln in open(p, encoding="utf-8", errors="replace"):
        m = re.match(r"FUNC\s+(\S+)", ln)
        if m:
            site = m.group(1)
            continue
        m = re.search(r"size=(\S+)\s+tiles=(\S+)\s+dst=(0x[0-9a-fA-F]+)", ln)
        if not m or m.group(2) == "-":
            continue
        d, n = int(m.group(3), 16), int(m.group(2))
        if VRAM <= d < VRAM + 0x10000:
            pages[site].append((d, n))
    # CPU 侧
    p = os.path.join(ROOT, ".tmp", "vram_cpu_assets_run.txt")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8", errors="replace"):
            m = re.match(r"0x([0-9a-f]{7})\s+(\d+)\s+(CpuSet|CpuFastSet)\s+\[(\d+)\]", ln)
            if not m:
                continue
            d, words = int(m.group(1), 16), int(m.group(4))
            if VRAM <= d < VRAM + 0x10000:
                pages["cpu:" + m.group(3)].append((d, max(1, words * 4 // 32)))
    return pages


def blocks_of(assets):
    """[(dst,tiles)] → {cb: set(块内砖号)}"""
    used = defaultdict(set)
    for d, n in assets:
        for k in range(n):
            a = d + k * 32
            if a >= VRAM + 0x10000:
                break
            used[(a - VRAM) // 0x4000].add(((a - VRAM) % 0x4000) // 32)
    return used


def main():
    rom = open(ROM, "rb").read()
    pages = load_page_blocks()
    page_blocks = {fn: blocks_of(ast) for fn, ast in pages.items()}
    page_addr = {int(fn, 16): fn for fn in pages if fn.startswith("0x")}

    # 模板
    tpls = []
    for a in range(TPL_LO, TPL_HI + 1, TPL_STEP):
        o = a - BASE
        tm, font = rom[o + 9], rom[o + 8]
        td = struct.unpack_from("<I", rom, o + 0x0C)[0]
        mp = struct.unpack_from("<I", rom, o + 0x10)[0]
        cb = (td - VRAM) // 0x4000 if VRAM <= td < VRAM + 0x10000 else -1
        tpls.append((a, tm, font, cb, td, mp))

    refs = scan_refs(rom, TPL_LO, TPL_HI)

    print("=" * 100)
    print("A. 模板 × 引用点 × 所属函数")
    print("=" * 100)
    pa = sorted(page_addr)
    tpl_owners = {}
    for a, tm, font, cb, td, mp in tpls:
        sites = sorted(refs.get(a, []))
        own = []
        for s in sites:
            o = owner(rom, s)
            own.append((s, o))
        # 把 owner 归属到「页面函数」（owner 落在某页面函数区间内？近似：owner >= page 且 < next page）
        hitpages = set()
        for s, o in own:
            if o is None:
                continue
            # 找 <= o 的最大页面地址，且 o 距它 < 0x2000
            cand = [x for x in pa if x <= o and o - x < 0x2000]
            if cand:
                hitpages.add(max(cand))
            # owner 自己就是页面函数
            if o in page_addr:
                hitpages.add(o)
        tpl_owners[a] = (own, hitpages)
        if not sites:
            print("%08X tm%d cb%d  tileData=%08X  —— 无引用点（无人直接引用）" % (a, tm, cb, td))
        else:
            print("%08X tm%d cb%d  tileData=%08X  引用 %d 处:" % (a, tm, cb, td, len(sites)))
            for s, o in own:
                pn = ""
                if o is not None:
                    pn = "owner %08X" % o
                    if o in page_addr:
                        pn += "  ★页面"
                    else:
                        cand = [x for x in pa if x <= o and o - x < 0x2000]
                        if cand:
                            pn += "  (近页面 %08X)" % max(cand)
                else:
                    pn = "owner ???"
                print("        @%08X  %s" % (s, pn))

    print()
    print("=" * 100)
    print("B. 每条模板的「真实可用槽」= 512 - |下一块 ∩ 该模板使用者的美术|")
    print("=" * 100)
    print("%-10s %-3s %-4s %-6s %-7s %-8s %s" %
          ("tpl", "tm", "cb", "下一块", "使用者数", "空闲砖", "占用该块的页面"))
    print("-" * 100)
    for a, tm, font, cb, td, mp in tpls:
        own, hitpages = tpl_owners[a]
        nxt = (cb + 1) if cb >= 0 else -1
        if cb == 3:
            nxt = -1                                # 号 512 起物理进 OBJ，BG 指不到
        if nxt < 0:
            print("%08X   %-3d %-4d %-6s %-7d %-8s %s" % (a, tm, cb, "—", len(hitpages), "N/A", "charBase=3 ⇒ 空集"))
            continue
        used = set()
        occ = []
        for fn in hitpages:
            ub = page_blocks.get(page_addr.get(fn, ""), {})
            s = ub.get(nxt, set())
            if s:
                occ.append("%08X(%d)" % (fn, len(s)))
            used |= s
        free = 512 - len(used)
        print("%08X   %-3d %-4d cb%-4d %-7d %-8d %s" %
              (a, tm, cb, nxt, len(hitpages), free if hitpages else -1,
               " ".join(occ) if occ else ("—（无使用者信息）" if not hitpages else "—(该块无人占)")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
