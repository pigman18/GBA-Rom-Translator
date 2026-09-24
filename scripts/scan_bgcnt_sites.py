#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""S1 静态分析：BGxCNT 写入点归类 + 官方 VRAM(cb2/cb3) 装载入口定位。

纯静态（不启动模拟器 / 不抓 gdb）。扫的是 **origin 原始 ROM**（不含我方 hook）。

方法：
  A) 找所有 `ldr rX, [pc, #imm]` 且池中字 == 0x04000008/0A/0C/0E  ⇒ rX 即某层 BGxCNT 地址
     再向前找第一条 `strh rX, [...]` ⇒ 写作点。
  B) 同理找池中字 == 0x04000000（BG 寄存器基址）⇒ 向前找 `strh rX, [rBase, #8/10/12/14]`。
  C) `movs rX,#0x80 ; lsls rX,rX,#19` 立即数构造 0x04000000，同上。
  D) 对每个写作点回溯最近的 `push {..., lr}` 认定为所属函数入口；按函数统计写了哪些层。
     分类：同函数写 >=2 个不同层 ⇒ 「逐层批量设置类」；否则 ⇒ 「单层场景配置类」。
  E) 池中字 == 0x06008000 / 0x0600C000（cb2 / cb3 起点）⇒ 定位官方往 cb2/cb3 装载的入口，
     并看其后续用法（DMA 寄存器 / BIOS swi / 直接 str / bl 拷贝函数）。

用法：
    python scripts/scan_bgcnt_sites.py                 # 打印 + 写 docs/S1_...md + out/s1_scan.json
    python scripts/scan_bgcnt_sites.py --top 40
"""
import os
import re
import sys
import json
import struct
from collections import defaultdict

import numpy as np
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000

BGCNT = {0x04000008: 0, 0x0400000A: 1, 0x0400000C: 2, 0x0400000E: 3}
BG_BASE = 0x04000000
CB2 = 0x06008000
CB3 = 0x0600C000
VRAM_BASE = 0x06000000
DMA_REGS = {0x040000B0 + 0xC * i + j: (i, j) for i in range(4)
            for j in (0, 4, 8)}  # SAD / DAD / CNT

MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
MD.detail = True


def rd32(raw, off):
    if 0 <= off and off + 4 <= len(raw):
        return struct.unpack_from("<I", raw, off)[0]
    return None


def rd16(raw, off):
    if 0 <= off and off + 2 <= len(raw):
        return struct.unpack_from("<H", raw, off)[0]
    return None


# ---------------------------------------------------------------- loaders
def find_literal_loaders(raw, want):
    """返回 [(loader_off, reg, value)]，要求池中字 == want。"""
    u16 = np.frombuffer(raw, dtype="<u2")
    n = u16.size
    idx = np.arange(n, dtype=np.int64)
    h = u16.astype(np.uint32)
    is_ldr = (h >> 11) == 0b01001          # LDR (literal)
    rt = (h >> 8) & 7
    imm = (h & 0xFF) * 4
    off = idx * 2
    lit = ((off + 4) & ~3) + imm
    sel = is_ldr & (lit + 4 <= len(raw))
    o_sel = off[sel]
    r_sel = rt[sel]
    l_sel = lit[sel]
    out = []
    for o, r, l in zip(o_sel, r_sel, l_sel):
        if rd32(raw, int(l)) == want:
            out.append((int(o), int(r), want))
    return out


def find_imm_base_loaders(raw):
    """`movs rX,#0x80 ; lsls rX,rX,#19` ⇒ 0x04000000。返回 [(lsls_off, reg)]"""
    u16 = np.frombuffer(raw, dtype="<u2")
    h = u16.astype(np.uint32)
    is_movs = (h & 0xF800) == 0x2000
    m_rt = (h >> 8) & 7
    m_imm = h & 0xFF
    is_lsl = ((h >> 11) & 0x1F) == 0
    l_imm5 = (h >> 6) & 0x1F
    l_rm = (h >> 3) & 7
    l_rd = h & 7
    out = []
    for i in range(len(u16) - 4):
        if not (is_movs[i] and m_imm[i] == 0x80):
            continue
        r = int(m_rt[i])
        for j in range(i + 1, min(i + 5, len(u16))):
            if is_lsl[j] and l_imm5[j] == 19 and l_rm[j] == r and l_rd[j] == r:
                out.append((int(j) * 2, r))
                break
    return out


def _dest_info(ins):
    """解析 store 的目标：返回 (base_reg, offset) 或 None。"""
    m = re.match(r"^\[?(r\d+)(?:,\s*#(-?0x[0-9a-f]+))?\]?", ins.op_str.split(",")[-1].strip()) \
        if False else None
    # 直接解析操作数
    ops = [o.strip() for o in ins.op_str.split(",")]
    if len(ops) < 2:
        return None
    mem = ", ".join(ops[1:]).strip()
    m = re.match(r"\[(r\d+)(?:,\s*#(-?0x[0-9a-fA-F]+))?\]", mem)
    if not m:
        return None
    base = m.group(1)
    off = int(m.group(2), 16) if m.group(2) else 0
    return base, off


def scan_forward_store(raw, start_off, reg, want_offsets, limit=80, stop_at_branch=True):
    """从 start_off 起反汇编，找第一条 `str* r{reg}, [base, #off]` 且 off ∈ want_offsets。
    返回 (addr, mnemonic, op_str, off) 或 None。"""
    code = raw[start_off:start_off + limit * 2]
    vma = BASE + start_off
    aliases = {f"r{reg}": 0}          # 寄存器 -> 相对 reg 的常量偏移
    seen = 0
    for ins in MD.disasm(code, vma):
        seen += 1
        m, ops = ins.mnemonic, [o.strip() for o in ins.op_str.split(",")]
        if m in ("strh", "str", "strb") and len(ops) >= 2:
            d = _dest_info(ins)
            if d:
                base, off = d
                if base in aliases:
                    eff = aliases[base] + off
                    if eff in want_offsets:
                        return (ins.address, m, ins.op_str, eff)
        # 别名传播
        if m in ("add", "adds") and len(ops) == 3:
            a, b, c = ops
            if b in aliases and c.startswith("#"):
                aliases[a] = aliases[b] + int(c[1:], 16)
        if m in ("mov", "movs") and len(ops) == 2 and ops[1] in aliases:
            aliases[ops[0]] = aliases[ops[1]]
        if seen > 12 and stop_at_branch and m in ("bl", "blx", "b", "bx") :
            break
        if seen > limit:
            break
    return None


def find_func_start(raw, addr):
    """回溯最近的 `push {..., lr}`（bit8=lr）。"""
    off = (addr - BASE) & ~1
    lo = max(0, off - 0x1000)
    for o in range(off, lo, -2):
        h = rd16(raw, o)
        if h is None:
            break
        if (h & 0xFE00) == 0xB400 and (h & 0x0100):
            # 再往前看 2 字节，若是同一个 push 的延续则继续
            prev = rd16(raw, o - 2)
            if prev is not None and (prev & 0xFE00) == 0xB400:
                continue
            return BASE + o
    return None


# ---------------------------------------------------------------- main scan
def collect_bgcnt_writes(raw):
    hits = {}   # addr -> dict

    def note(addr, layer, mode):
        d = hits.setdefault(addr, {"vma": addr, "layers": set(), "modes": []})
        d["layers"].add(layer)
        if mode not in d["modes"]:
            d["modes"].append(mode)

    # A/B: 直接写 BGxCNT 地址
    for want, layer in BGCNT.items():
        for lo_off, reg, _ in find_literal_loaders(raw, want):
            r = scan_forward_store(raw, lo_off, reg, {0})
            if r:
                note(r[0], layer, "literal-BGxCNT")
    # C: 基址 0x04000000 的字面量 + strh offset 8..14
    for lo_off, reg, _ in find_literal_loaders(raw, BG_BASE):
        r = scan_forward_store(raw, lo_off, reg, {8, 10, 12, 14})
        if r:
            note(r[0], BGCNT[BG_BASE + r[3]], "literal-basereg")
    # D: movs/lsls 立即数构造
    for lo_off, reg in find_imm_base_loaders(raw):
        r = scan_forward_store(raw, lo_off, reg, {8, 10, 12, 14})
        if r:
            note(r[0], BGCNT[BG_BASE + r[3]], "imm-basereg")

    # 归并：同一地址可能被多次命中
    out = []
    for addr in sorted(hits):
        d = hits[addr]
        fn = find_func_start(raw, addr)
        out.append({
            "vma": addr,
            "hex": "0x%08X" % addr,
            "layers": sorted(d["layers"]),
            "modes": d["modes"],
            "func": fn,
            "func_hex": ("0x%08X" % fn) if fn else None,
        })
    return out


def collect_vram_entry(raw, target, label):
    """找往 cb2/cb3 装载的入口：池中字 == target，看其后用法。"""
    res = []
    for lo_off, reg, _ in find_literal_loaders(raw, target):
        code = raw[lo_off:lo_off + 2 * 30]
        vma = BASE + lo_off
        uses = []
        seen = 0
        for ins in MD.disasm(code, vma):
            seen += 1
            m, ops = ins.mnemonic, [o.strip() for o in ins.op_str.split(",")]
            tag = None
            if m in ("str", "strh") and ops and ops[0] == f"r{reg}":
                tag = "STORE"
            elif m in ("bl", "blx"):
                tag = "CALL " + (ops[0] if ops else "")
            elif m == "swi":
                tag = "SWI " + (ops[0] if ops else "")
            elif m in ("mov", "movs", "add", "adds", "lsl", "lsls") and ops and f"r{reg}" in ops:
                tag = "MOVE"
            if tag:
                uses.append("%08X: %-6s %-22s ; %s" % (ins.address, m, ins.op_str, tag))
            if seen >= 14:
                break
        res.append({
            "loader": "0x%08X" % (BASE + lo_off),
            "reg": "r%d" % reg,
            "func": ("0x%08X" % find_func_start(raw, BASE + lo_off))
            if find_func_start(raw, BASE + lo_off) else None,
            "uses": uses,
        })
    return res


def main():
    top = 40
    if "--top" in sys.argv:
        top = int(sys.argv[sys.argv.index("--top") + 1])

    raw = open(ROM, "rb").read()
    print("ROM: %s  (%d bytes)" % (ROM, len(raw)))

    sites = collect_bgcnt_writes(raw)
    print("\n=== A. BGxCNT 写入点：共 %d 处 ===" % len(sites))

    byfunc = defaultdict(list)
    for s in sites:
        byfunc[s["func_hex"]].append(s)

    multi, single = [], []
    for fn, lst in byfunc.items():
        layers = set()
        for s in lst:
            layers.update(s["layers"])
        (multi if len(layers) >= 2 else single).append((fn, lst, sorted(layers)))

    print("\n--- 逐层批量设置类（同函数写 >=2 层）：%d 个函数 ---" % len(multi))
    for fn, lst, layers in sorted(multi, key=lambda x: (x[0] or "")):
        print("  func %s  layers=%s  sites=%s" % (
            fn, layers, [s["hex"] for s in lst]))

    print("\n--- 单层场景配置类：%d 个函数 / %d 处 ---" % (
        len(single), sum(len(x[1]) for x in single)))
    for fn, lst, layers in sorted(single, key=lambda x: (x[0] or ""))[:top]:
        for s in lst:
            print("  fn %s  site %s  layer=BG%s  mode=%s" % (
                fn, s["hex"], s["layers"][0], ",".join(s["modes"])))

    print("\n=== B. 官方 cb2/cb3 装载入口 ===")
    cb2 = collect_vram_entry(raw, CB2, "cb2")
    cb3 = collect_vram_entry(raw, CB3, "cb3")
    print("-- cb2 (0x06008000): %d 个引用点 --" % len(cb2))
    for e in cb2:
        print("  loader %s %s  func=%s" % (e["loader"], e["reg"], e["func"]))
        for u in e["uses"]:
            print("      " + u)
    print("-- cb3 (0x0600C000): %d 个引用点 --" % len(cb3))
    for e in cb3:
        print("  loader %s %s  func=%s" % (e["loader"], e["reg"], e["func"]))
        for u in e["uses"]:
            print("      " + u)

    # 落盘
    outdir = os.path.join(ROOT, "out")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "s1_scan.json"), "w", encoding="utf-8") as f:
        json.dump({
            "sites": [{**s, "layers": s["layers"]} for s in sites],
            "multi": [{"func": f, "layers": l, "sites": [s["hex"] for s in ss]}
                      for f, ss, l in multi],
            "single": [{"func": f, "layers": l, "sites": [s["hex"] for s in ss]}
                       for f, ss, l in single],
            "cb2": cb2, "cb3": cb3,
        }, f, ensure_ascii=False, indent=1)
    print("\n[written] out/s1_scan.json")


if __name__ == "__main__":
    main()
