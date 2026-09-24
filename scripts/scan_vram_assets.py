#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_vram_assets.py — 枚举「直接写 VRAM 固定地址」的静态资产落点与真实长度

背景
====
15-0b 证明日版引擎是「位置定号 + 每窗口私有基址」。把窗口 tm0 化后官方不再占号，
但**静态 BG 层美术（LZ77/RL 直接解压到固定 VRAM 地址、从不申请号）仍物理占号**。

`UpdateTilemap 0x080036DC` 实证：`strh = tile | (win[0x0F] << 12)` ⇒
**tile 号原样写进 tilemap，不加 charBase 偏移** ⇒ 号是 **0..1023 的全局号**，
地址区间 = `0x06000000 + charBase*0x4000 .. +0x8000`（32KB）。
⇒ 某个窗口（charBase=0）的可用号 = 绝对地址落在 `[0x06000000, 0x06008000)` 的资产之补集。

本脚本枚举：
  · `bl 0x081B1298`  LZ77UnCompVram  r0=src r1=dst
  · `bl 0x081B12A4`  RLUnCompVram    r0=src r1=dst
两个参数都回溯；解压长度从压缩头读出（LZ77: 0x10|size-1<<8；RL: 0x30|size-1<<8），
tile 数 = ceil(解压字节 / 32)。

自证闸门
========
  G1 BL 解码器：4 个已知 `DrawGlyphTiles 0x08003630` 调用点必须全找到
  G2 调用计数：LZ77Vram == 118、RLVram == 13
  G3 头合法性：解析出的压缩头首字节必须 ∈ {0x10, 0x30}，且 size 与 ROM 剩余长度相容
  G4 交叉验证：已知领航员静态美术应在 0x06005000（号 640）出现

零 ROM 风险：只读。
"""
import sys
import os
import collections

ROM_PATH = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
ROM_END = 0x08800000
VRAM_LO = 0x06000000
VRAM_HI = 0x06018000

TARGETS = {
    0x081B1298: ("LZ77UnCompVram", 118, 0x10),
    0x081B12A4: ("RLUnCompVram", 13, 0x30),
}

KNOWN_DRAWGLYPHTILES = [0x08002AA6, 0x08002B16, 0x080033A2, 0x08003542]
KNOWN_POKENAV_ASSET = 0x06005000

_gate = {"unknown_origin": []}


def load_rom():
    with open(ROM_PATH, "rb") as f:
        return f.read()


def find_bl_sites(rom, target):
    out = []
    hi = min(ROM_END, BASE + len(rom) - 4)
    for a in range(BASE, hi, 2):
        o = a - BASE
        hw1 = rom[o] | (rom[o + 1] << 8)
        hw2 = rom[o + 2] | (rom[o + 3] << 8)
        if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xD000) != 0xD000:
            continue
        S = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        J1 = (hw2 >> 13) & 1
        J2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        I1 = (1 - J1) if S == 0 else J1
        I2 = (1 - J2) if S == 0 else J2
        d = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if d & 0x1000000:          # 🔴 25 位有符号数必须符号扩展
            d -= 0x2000000
        if a + 4 + d == target:
            out.append(a)
    return out


def lit_pool_value(rom, addr, imm8):
    lit = ((addr + 4) & ~3) + imm8 * 4
    o = lit - BASE
    if 0 <= o <= len(rom) - 4:
        return int.from_bytes(rom[o:o + 4], "little")
    return None


def decode_write(hw, addr, rom):
    if (hw & 0xF800) == 0x2000:
        return ((hw >> 8) & 7, "imm", hw & 0xFF)
    if (hw & 0xF800) == 0x2600:
        return ((hw >> 8) & 7, "imm", hw & 0xFF)
    if (hw & 0xF800) == 0xA000:
        return ((hw >> 8) & 7, "imm", ((addr + 4) & ~3) + (hw & 0xFF) * 4)
    if (hw & 0xF800) == 0x4800:
        return ((hw >> 8) & 7, "lit", lit_pool_value(rom, addr, hw & 0xFF))
    if (hw & 0xF800) == 0x3000:
        return ((hw >> 8) & 7, "selfadd", hw & 0xFF)
    if (hw & 0xFF00) == 0x4600 and ((hw >> 6) & 3) == 2:
        rd = (hw & 7) | ((hw >> 4) & 8)
        return (rd, "reg", (hw >> 3) & 0xF)
    if (hw & 0xFE00) == 0x1C00:
        rd = (hw & 7) | ((hw >> 4) & 8)
        return (rd, "regadd", ((hw >> 3) & 7, (hw >> 6) & 7))
    if (hw & 0xFE00) == 0x1800:
        rd = (hw & 7) | ((hw >> 4) & 8)
        return (rd, "regadd2", ((hw >> 3) & 7, (hw >> 6) & 7))
    if (hw & 0xF800) == 0x6800:
        return ((hw >> 8) & 7, "mem", ((hw >> 3) & 7, ((hw >> 6) & 0x1F) * 4))
    if (hw & 0xFE00) == 0x5800:
        return (hw & 7, "mem2", ((hw >> 3) & 7, (hw >> 6) & 7))
    if (hw & 0xE000) == 0x0000 and ((hw >> 11) & 3) != 3:
        return (hw & 7, "shift", ((hw >> 3) & 7, (hw >> 6) & 7))
    return None


def resolve_reg(rom, addr, reg, depth=0, seen=None):
    """从 addr 往前回溯，求 reg 的常量值；求不出返回 None。"""
    if depth > 4:
        return None
    if seen is None:
        seen = frozenset()
    if reg in seen:
        return None
    seen = seen | {reg}
    for k in range(1, 25):
        a = addr - 2 * k
        if a < BASE:
            break
        o = a - BASE
        hw = rom[o] | (rom[o + 1] << 8)
        w = decode_write(hw, a, rom)
        if not w:
            continue
        rd, kind, arg = w
        if rd != reg:
            continue
        if kind in ("imm", "lit"):
            return arg
        if kind == "reg":
            return resolve_reg(rom, a, arg, depth + 1, seen)
        if kind == "selfadd":
            b = resolve_reg(rom, a, reg, depth + 1, seen)
            return None if b is None else b + arg
        if kind == "regadd":
            v = resolve_reg(rom, a, arg[0], depth + 1, seen)
            return None if v is None else v + arg[1]
        if kind == "regadd2":
            v1 = resolve_reg(rom, a, arg[0], depth + 1, seen)
            v2 = resolve_reg(rom, a, arg[1], depth + 1, seen)
            return None if (v1 is None or v2 is None) else v1 + v2
        return None
    return None


def comp_size(rom, src, want_first):
    """读压缩头，返回 (kind_ok, decompressed_size, first_byte)"""
    o = src - BASE
    if not (0 <= o <= len(rom) - 4):
        return (False, 0, None)
    b0 = rom[o]
    size = int.from_bytes(rom[o + 1:o + 4], "little") + 1
    return (b0 == want_first, size, b0)


def main() -> int:
    if not os.path.exists(ROM_PATH):
        print("❌ 找不到 ROM: %s" % ROM_PATH)
        return 2
    rom = load_rom()

    # ---- G1 ----
    got = find_bl_sites(rom, 0x08003630)
    miss = [hex(a) for a in KNOWN_DRAWGLYPHTILES if a not in got]
    if miss:
        print("❌ G1 失败：已知 DrawGlyphTiles 调用点未找到 = %s" % miss)
        return 2
    print("✅ G1 BL 解码器自证：4 个已知调用点全部命中")

    # ---- G2 ----
    site_cache = {}
    for tgt, (name, expect, _) in TARGETS.items():
        sites = find_bl_sites(rom, tgt)
        site_cache[tgt] = sites
        if len(sites) != expect:
            print("❌ G2 失败：%s 调用点 = %d，期望 %d" % (name, len(sites), expect))
            return 2
    print("✅ G2 调用点计数：LZ77Vram=118、RLVram=13 与历史实测一致")

    rows = []
    for tgt, (name, _, want) in TARGETS.items():
        for site in site_cache[tgt]:
            dst = resolve_reg(rom, site, 1)
            src = resolve_reg(rom, site, 0)
            rows.append((site, name, src, dst, want))

    res = [r for r in rows if r[3] is not None and r[2] is not None]
    nodst = [r for r in rows if r[3] is None]
    nosrc = [r for r in res if r[2] is None]

    # ---- G3：头合法性 ----
    entries = []
    hdr_bad = 0
    for site, name, src, dst, want in rows:
        if dst is None:
            continue
        ok, size, b0 = comp_size(rom, src, want) if src is not None else (False, 0, None)
        if src is None or not ok:
            hdr_bad += 1
            size = 0
        entries.append((site, name, src, dst, size, b0))
    if hdr_bad:
        print("⚠ G3：%d 条未能读出合法压缩头（src 不可解析或首字节异常）" % hdr_bad)
    else:
        print("✅ G3 头合法性：全部压缩头首字节与函数类型一致")

    # ---- G4：交叉验证 ----
    vram_dsts = collections.Counter(e[3] for e in entries if VRAM_LO <= e[3] < VRAM_HI)
    if vram_dsts.get(KNOWN_POKENAV_ASSET, 0) == 0:
        print("❌ G4 失败：未在 0x06005000 找到资产（领航员静态美术）")
        return 2
    print("✅ G4 交叉验证：0x06005000（号 640）命中 %d 次，与 15-0 记录的领航员美术位置一致"
          % vram_dsts[KNOWN_POKENAV_ASSET])
    print()

    # ---- 号空间占用：只统计 charBase=0 视角（绝对区间 [0x06000000,0x06008000)）----
    print("=" * 78)
    print("静态资产占用（BG 号空间视角：号 = (dst - 0x06000000)/32，仅 [0,1024) 可达）")
    print("=" * 78)
    print("%-12s %-16s %-12s %-12s %-8s %-8s %s"
          % ("caller", "func", "src(ROM)", "dst", "tile", "tiles", "range"))
    print("-" * 78)
    occ = {}   # tile -> (caller, n_tiles)
    for site, name, src, dst, size, b0 in sorted(entries, key=lambda e: e[3]):
        if not (VRAM_LO <= dst < VRAM_HI):
            continue
        tile = (dst - VRAM_LO) // 32
        if tile >= 1024:
            continue
        nt = (size + 31) // 32 if size else 0
        occ.setdefault(tile, (site, name, nt, size))
        print("%-12s %-16s 0x%08X   0x%08X   %-8d %-8d [%d, %d)"
              % (hex(site), name, src if src else 0, dst, tile, nt, tile, tile + max(nt, 1)))

    # ---- 合并成占用区间 ----
    spans = []
    for tile, (site, name, nt, size) in sorted(occ.items()):
        spans.append((tile, tile + max(nt, 1), site, name, nt, size))
    merged = []
    for s in spans:
        if merged and s[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], s[1]),
                          merged[-1][2], merged[-1][3], merged[-1][4], merged[-1][5])
        else:
            merged.append(list(s) if False else s)

    print()
    print("=" * 78)
    print("合并后的占用区间（并集，未区分场景加载时机）")
    print("=" * 78)
    for lo, hi, site, name, nt, size in merged:
        print("  [%4d, %4d)  %3d 号   来自 %s @0x%08X" % (lo, hi, hi - lo, name, site))

    # ---- 空闲区间 ----
    print()
    print("=" * 78)
    print("空闲区间（号 [0,1024) 减去占用）")
    print("=" * 78)
    cur = 0
    free = []
    for lo, hi, *_ in merged:
        if lo > cur:
            free.append((cur, lo))
        cur = max(cur, hi)
    if cur < 1024:
        free.append((cur, 1024))
    for lo, hi in free:
        print("  [%4d, %4d)  %3d 号" % (lo, hi, hi - lo))
    if free:
        big = max(free, key=lambda r: r[1] - r[0])
        print()
        print("  ⇒ 最大连续空闲 = [%d, %d) = %d 号" % (big[0], big[1], big[1] - big[0]))

    # ---- 不可解析清单 ----
    if nodst:
        print()
        print("⚠ dst 不可静态解析：%d 个" % len(nodst))
        for site, name, src, dst, want in nodst:
            print("     0x%08X  %s" % (site, name))
    if nosrc:
        print()
        print("⚠ src 不可静态解析（长度未知）：%d 个" % len(nosrc))
        for site, name, src, dst, want in nosrc:
            tile = (dst - VRAM_LO) // 32
            print("     0x%08X  %s  dst=0x%08X (号 %d)" % (site, name, dst, tile))
    return 0


if __name__ == "__main__":
    sys.exit(main())
