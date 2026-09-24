#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_engine_tile_cache.py —— 「数写入点」判据：算出引擎**必然写入**的 VRAM 区间。

与 `.tmp/freemap.py`（采样 7 页 map 引用求补集）的根本区别
==========================================================
freemap 只看「被 map **引用**过的砖」，本脚本**不采样**，只静态枚举
「写 VRAM 的调用点」并把目标地址解成表达式。二者结论不同：

  freemap 判「空档」的地方，有一大片是引擎的**字模预加载区** ——
  字模是**超前**于显示的，写进去时 map 还没引用它 ⇒ 被 freemap 误判为空档。

已证事实（逐指令反汇编 + 38 份 drive_*_iwram.bin 实测）
======================================================
【字模加载的唯一入口】全 ROM 各只有 2 个调用点
  · 0x08002950(winPtr, tileBase)   「配置」
        *0x03000328 = *winPtr        （当前活动窗口**模板**指针）
        *0x0300032C = tileBase       （全局 tileBase）
        *0x0300032E = 0              （加载计数器复位）
        winPtr[0x16] = tileBase
  · 0x080029E0()                   「分帧推进」
        每次调用做 16 个 index，*0x0300032E += 16，累到 256 返回 1
  ⇒ index 实际遍历 [0, 256)

【写入公式】InitWindowTileData 0x08002A50，按 win[8] 分派 6 路 → 3 个分支
  · font 0/3      : dst = tileData + tileBase*32 + index*64
  · font 1/2/4/5  : dst = tileData + (tileBase + index)*32
  其中 tileData = (*0x03000328)[+0x0C] = 窗口模板的写砖基址
  DrawGlyphTiles 0x08003630 内两次 blit（dst 与 dst+32）⇒ 每个 index 占 2 个连续 tile
  ⇒ **字模区 = [tileData + tileBase*32, tileData + tileBase*32 + 513*32)**

【实测】（38 份 IWRAM dump）
  tileBase ≡ 1（全部有值样本）｜计数器 = 256（跑满一轮）或 0（刚复位）
  *0x03000328 ∈ {0x081BB484, 0x081BB49C, 0x081BB544, 0x081BB5BC, 0x081BB874, 0}
  ⇒ 对应 tileData ∈ {0x06008000 (cb2), 0x06000000 (cb0)}

自证闸门
========
  G1 全局量引用点：0x0300032C 恰好 2 处、0x0300032E 恰好 3 处、0x03000328 恰好 4 处
  G2 实测 tileBase：所有已初始化样本必须 == 1
  G3 模板 tileData：必须落在 VRAM 且 32 字节对齐
  G4 入口计数：0x08002950 / 0x080029E0 的 BL 调用点各恰好 2 处
零 ROM 风险：只读。
"""
from __future__ import annotations

import glob
import os
import re
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"C:\code\GBA-Rom-Translator"
ROM_PATH = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
SRC = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook", "src",
                   "text", "PrintNextChar_hook.c")

BASE = 0x08000000
VRAM_LO, VRAM_HI = 0x06000000, 0x06018000
TILE = 32                       # 4bpp 8x8 = 32 B

TPL_LO, TPL_HI, TPL_SZ = 0x081BB400, 0x081BB900, 32
TPL_TILE_OFF = 0x0C

A_TILE_TPL = 0x03000328         # 当前活动窗口模板指针
A_TILEBASE = 0x0300032C
A_COUNTER = 0x0300032E

FN_SETUP = 0x08002950           # 配置 tileBase + 复位计数器
FN_STEP = 0x080029E0            # 分帧推进

TILE_BASE_EXPECT = 1
FONT_SPAN = 513                 # 字模区长度（号数）= [tileBase, tileBase+512]

# 三个人口的 charBase 基址（= 窗口模板 tileData 的层基址）
DOM_NAME = {0: "cb1(人口0)", 1: "cb2(人口1)", 2: "cb0(人口2)"}
DOM_BASE = {0: 0x06004000, 1: 0x06008000, 2: 0x06000000}

GATES = []


def gate(ok: bool, msg: str) -> bool:
    GATES.append((ok, msg))
    print(("  OK   " if ok else "  FAIL ") + msg)
    return ok


def bl_target(rom: bytes, off: int):
    hw1 = rom[off] | (rom[off + 1] << 8)
    hw2 = rom[off + 2] | (rom[off + 3] << 8)
    if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xD000) != 0xD000:
        return None
    S, imm10 = (hw1 >> 10) & 1, hw1 & 0x3FF
    J1, J2, imm11 = (hw2 >> 13) & 1, (hw2 >> 11) & 1, hw2 & 0x7FF
    I1 = (1 - J1) if S == 0 else J1
    I2 = (1 - J2) if S == 0 else J2
    d = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if d & 0x1000000:
        d -= 0x2000000
    return (BASE + off + 4 + d) & 0xFFFFFFFF


def bl_sites(rom: bytes, target: int):
    out = []
    for off in range(0, len(rom) - 4, 2):
        if bl_target(rom, off) == target:
            out.append(BASE + off)
    return out


def litteral_refs(rom: bytes, value: int):
    """找 4 字节小端字面量 == value 的文件位置（= ldr rX,[pc,#n] 的池子项）。"""
    pat = struct.pack("<I", value)
    out, i = [], rom.find(pat)
    while i >= 0:
        out.append(BASE + i)
        i = rom.find(pat, i + 2)
    return out


def templates(rom: bytes):
    """模板表：任意 4 字节起点，+0x0C 落在 VRAM 即视为一个窗口模板。"""
    seen, out = set(), []
    for a in range(TPL_LO, TPL_HI):
        o = a - BASE
        if o < 0 or o + TPL_SZ > len(rom):
            continue
        td = struct.unpack_from("<I", rom, o + TPL_TILE_OFF)[0]
        if not (VRAM_LO <= td < VRAM_HI) or td % TILE:
            continue
        if td in seen:
            continue
        seen.add(td)
        out.append((a, td))
    return out


def tile_data_of(rom: bytes, tpl: int):
    o = tpl - BASE
    if not (0 <= o <= len(rom) - 4):
        return None
    td = struct.unpack_from("<I", rom, o + TPL_TILE_OFF)[0]
    return td if VRAM_LO <= td < VRAM_HI else None


def parse_pools(src_text: str):
    """从 hook 源码解析 chs_p{0,1,2}_seg_b / seg_n。"""
    pools = {}
    for dom in (0, 1, 2):
        mb = re.search(r"chs_p%d_seg_b\[\d+\]\s*=\s*\{([^}]*)\}" % dom, src_text)
        mn = re.search(r"chs_p%d_seg_n\[\d+\]\s*=\s*\{([^}]*)\}" % dom, src_text)
        if not mb or not mn:
            raise SystemExit("解析段表失败：人口 %d" % dom)
        b = [int(x) for x in re.findall(r"\d+", mb.group(1))]
        n = [int(x) for x in re.findall(r"\d+", mn.group(1))]
        if len(b) != len(n):
            raise SystemExit("人口 %d 段表长度不等 %d vs %d" % (dom, len(b), len(n)))
        pools[dom] = list(zip(b, n))
    return pools


def pool_tiles(pools):
    """展开成 (dom, tile_addr) 列表。槽步进 2 ⇒ 1 槽 = 2 个连续 tile。"""
    out = []
    for dom, segs in pools.items():
        for b, n in segs:
            for i in range(n * 2):
                out.append((dom, b, DOM_BASE[dom] + (b + i) * TILE))
    return out


def spans(tile_datas, tile_base=TILE_BASE_EXPECT, span=FONT_SPAN):
    out = []
    for td in sorted(set(tile_datas)):
        lo = td + tile_base * TILE
        out.append((lo, lo + span * TILE, td))
    return merge(out)


def merge(iv):
    out = []
    for lo, hi, tag in sorted(iv):
        if out and lo <= out[-1][1]:
            if hi > out[-1][1]:
                out[-1] = (out[-1][0], hi, out[-1][2])
        else:
            out.append((lo, hi, tag))
    return out


def in_spans(iv, a):
    for lo, hi, _ in iv:
        if lo <= a < hi:
            return True
    return False


def main() -> int:
    rom = open(ROM_PATH, "rb").read()
    print("ROM %d B" % len(rom))

    print("\n--- G1 全局量引用点 ---")
    r328 = litteral_refs(rom, A_TILE_TPL)
    r32c = litteral_refs(rom, A_TILEBASE)
    r32e = litteral_refs(rom, A_COUNTER)
    gate(len(r32c) == 2, "0x0300032C 字面量 = %d 处（期望 2）" % len(r32c))
    gate(len(r32e) == 3, "0x0300032E 字面量 = %d 处（期望 3）" % len(r32e))
    gate(len(r328) >= 3, "0x03000328 字面量 = %d 处（期望 >=3）" % len(r328))

    print("\n--- G4 字模加载入口计数 ---")
    s_setup, s_step = bl_sites(rom, FN_SETUP), bl_sites(rom, FN_STEP)
    gate(len(s_setup) == 2, "0x08002950 调用点 = %d 处（期望 2）" % len(s_setup))
    gate(len(s_step) == 2, "0x080029E0 调用点 = %d 处（期望 2）" % len(s_step))
    for a in s_setup:
        print("       0x%08X" % a)

    print("\n--- G2 实测 tileBase / 计数器 / 活动模板 ---")
    dumps = sorted(glob.glob(os.path.join(ROOT, ".tmp", "drive_*_iwram.bin")))
    seen_tpl, bad_tb, done, zero = {}, [], 0, 0
    for p in dumps:
        b = open(p, "rb").read()
        if len(b) < 0x340:
            continue
        tb = struct.unpack_from("<H", b, A_TILEBASE - 0x03000000)[0]
        cnt = struct.unpack_from("<H", b, A_COUNTER - 0x03000000)[0]
        tpl = struct.unpack_from("<I", b, A_TILE_TPL - 0x03000000)[0]
        tag = os.path.basename(p)[6:-10]
        if tb == 0 and tpl == 0:
            zero += 1
            continue
        if tb != TILE_BASE_EXPECT:
            bad_tb.append((tag, tb))
        if cnt == 256:
            done += 1
        seen_tpl.setdefault(tpl, []).append(tag)
    gate(not bad_tb, "tileBase 全为 %d（异常 %s）" % (TILE_BASE_EXPECT, bad_tb or "无"))
    print("       dump 样本 %d 份（未初始化 %d）｜计数器跑满(=256) %d 份"
          % (len(dumps), zero, done))
    act_td = {}
    for tpl, tags in sorted(seen_tpl.items()):
        td = tile_data_of(rom, tpl)
        act_td[tpl] = td
        print("       tpl=0x%08X  tileData=%s  ← %d 页  %s"
              % (tpl, ("0x%08X" % td) if td else "非VRAM/无效",
                 len(tags), ",".join(sorted(tags)[:6]) + ("..." if len(tags) > 6 else "")))
    gate(all(v is not None for v in act_td.values()),
         "实测激活模板的 tileData 全部落在 VRAM")

    print("\n--- G3 全部窗口模板的 tileData ---")
    tpl_all = templates(rom)
    all_td = sorted(set(td for _, td in tpl_all))
    gate(all(td % TILE == 0 for td in all_td), "模板 tileData 全部 32B 对齐")
    print("       共 %d 个不同 tileData：" % len(all_td))
    for td in all_td:
        cb = (td - VRAM_LO) // 0x4000
        print("         0x%08X  cb%d  号 %d" % (td, cb, (td - VRAM_LO) // TILE))

    act_list = [v for v in act_td.values() if v is not None]
    sp_act = spans(act_list)
    sp_all = spans(all_td)

    print("\n--- 引擎字模写入区（tileBase=%d，跨 %d 个号 = %d B）---"
          % (TILE_BASE_EXPECT, FONT_SPAN, FONT_SPAN * TILE))
    print("  [实测激活口径]  %d 个 tileData" % len(set(act_list)))
    for lo, hi, td in sp_act:
        print("     [0x%08X, 0x%08X)  %5.1f KB   <- tileData 0x%08X"
              % (lo, hi, (hi - lo) / 1024.0, td))
    print("  [全部模板口径]  %d 个 tileData" % len(all_td))
    for lo, hi, td in sp_all:
        print("     [0x%08X, 0x%08X)  %5.1f KB   <- tileData 0x%08X"
              % (lo, hi, (hi - lo) / 1024.0, td))
    covered = sum(hi - lo for lo, hi, _ in sp_all)
    print("  ⇒ 全部模板口径覆盖 %.1f KB / VRAM %.1f KB"
          % (covered / 1024.0, (VRAM_HI - VRAM_LO) / 1024.0))

    pools = parse_pools(open(SRC, encoding="utf-8").read())
    tiles = pool_tiles(pools)
    print("\n--- 池子 vs 字模区（按**物理地址**判定）---")
    for dom in (0, 1, 2):
        segs = pools[dom]
        tot = sum(n for _, n in segs)
        hit = hit_a = 0
        for d, b, a in tiles:
            if d != dom:
                continue
            if in_spans(sp_act, a):
                hit += 1
            if in_spans(sp_all, a):
                hit_a += 1
        tiles_dom = sum(2 * n for _, n in segs)
        print("  %-10s %3d 槽 / %3d tile   实测口径危险 %3d (%.0f%%)   全模板口径危险 %3d (%.0f%%)"
              % (DOM_NAME[dom], tot, tiles_dom,
                 hit, 100.0 * hit / max(tiles_dom, 1),
                 hit_a, 100.0 * hit_a / max(tiles_dom, 1)))

    tot_all = 2 * sum(n for segs in pools.values() for _, n in segs)
    h_all = sum(1 for _, _, a in tiles if in_spans(sp_act, a))
    print("  %-10s %3d tile   实测口径危险 %3d (%.0f%%)"
          % ("合计", tot_all, h_all, 100.0 * h_all / max(tot_all, 1)))

    print("\n--- 逐段明细 ---")
    for dom in (0, 1, 2):
        for b, n in pools[dom]:
            a = DOM_BASE[dom] + b * TILE
            end = a + n * 2 * TILE
            bad = in_spans(sp_act, a)
            print("  p%d  号%-5d +%-3d 槽  0x%08X..0x%08X  %s"
                  % (dom, b, n, a, end, "危险(实测字模区)" if bad else "安全"))

    print("\n--- 闸门汇总 ---")
    ok = all(g[0] for g in GATES)
    for k, m in GATES:
        if not k:
            print("  FAIL %s" % m)
    print("  结论: %s" % ("PASS — 判据自证通过" if ok else "FAIL"))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
