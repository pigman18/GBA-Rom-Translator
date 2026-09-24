#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_diag_log.py — 解析 diag_log.c 的采样块（默认 0x0203C000）

用法:
    python scripts/analyze_diag_log.py .tmp/gdb_ewram.bin

回答三个问题：
  ① 门控过不过 / tpl->tileData 真值
  ② 同屏几个中文窗口
  ③ PrintNextChar 实际写下去的 tile 号 / 偏移 / tm

🔬 只读：不改任何产物。
"""
import struct
import sys

DIAG = 0x0203C000
EWRAM = 0x02000000
MAGIC = 0x31445841

RC = {0: "PASS", 1: "FAIL:tileData!=0x06000000", 2: "FAIL:tm>=2", 3: "FAIL:no win/tpl"}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ".tmp/gdb_ewram.bin"
    d = open(path, "rb").read()
    off = DIAG - EWRAM
    if off + 3072 > len(d):
        print("dump 太短（需要覆盖 0x0203C000..0x0203CBFF）：", len(d))
        return 1

    w = [struct.unpack_from("<I", d, off + i * 4)[0] for i in range(768)]

    if w[0] != MAGIC:
        print(f"❌ magic=0x{w[0]:08X}（应为 0x{MAGIC:08X}）⇒ 诊断块没被写过")
        print("   ⇒ 说明 InitTextPrinter_hook_C 一次都没被调用（或块地址被覆盖）。")
        return 2

    print("=" * 70)
    print("① 计数（cumulative）")
    print("=" * 70)
    print(f"  InitTextPrinter 钩子调用   : {w[1]}")
    print(f"    门控 PASS               : {w[2]}")
    print(f"    失败 tileData != 06000000: {w[3]}")
    print(f"    失败 tm >= 2            : {w[4]}")
    print(f"    失败 win/tpl 空          : {w[5]}")
    print(f"  中文字形落砖 (PNC)         : {w[6]}")
    print(f"  chs_canvas_base_for 调用   : {w[7]}")
    print(f"  不同窗口实例数             : {w[8]}")
    print(f"  最后一次 INIT: win=0x{w[9]:08X} tpl=0x{w[10]:08X} "
          f"tileData=0x{w[11]:08X} tbase=0x{w[12]:04X} tm={w[13]} "
          f"tpl9={w[14]} canvas={w[15]}")

    print()
    print("=" * 70)
    print("① b 门控判的那个 tpl->tileData 出现过哪些值")
    print("=" * 70)
    any_td = False
    for i in range(16):
        v, c = w[736 + i * 2], w[736 + i * 2 + 1]
        if c:
            any_td = True
            mark = "  ← 门控要的就是它" if v == 0x06000000 else ""
            print(f"  0x{v:08X}  ×{c}{mark}")
    if not any_td:
        print("  （无）")

    print()
    print("=" * 70)
    print("② 不同窗口实例（同屏几个中文窗口）")
    print("=" * 70)
    n = min(w[8], 48)
    if n == 0:
        print("  （无）")
    for i in range(n):
        win, cap, tmrc = w[16 + i * 3], w[16 + i * 3 + 1], w[16 + i * 3 + 2]
        tm = (tmrc >> 8) & 0xFF
        rc = tmrc & 0xFF
        print(f"  #{i:<2} win=0x{win:08X} canvas={cap:<5} tm={tm} rc={RC.get(rc, rc)}")

    print()
    print("=" * 70)
    print("③ INIT 环形（最近 32 条，按发生顺序）")
    print("=" * 70)
    calls = w[1]
    cnt = min(calls, 32)
    start = (calls - cnt) % 32
    for k in range(cnt):
        e = (start + k) % 32
        o = 160 + e * 6
        if w[o] != 1:
            continue
        tbase_tm = w[o + 4]
        tpl9_cap = w[o + 5]
        print(f"  win=0x{w[o+1]:08X} tpl=0x{w[o+2]:08X} tileData=0x{w[o+3]:08X} "
              f"tbase=0x{tbase_tm & 0xFFFF:04X} tm={tbase_tm >> 16} "
              f"tpl9={tpl9_cap & 0xFFFF} canvas={tpl9_cap >> 16}")

    print()
    print("=" * 70)
    print("④ PNC 环形（最近 64 个中文字形落砖）")
    print("=" * 70)
    pc = w[6]
    if pc == 0:
        print("  （无：这次运行没画过中文）")
    else:
        cnt = min(pc, 64)
        start = (pc - cnt) % 64
        for k in range(cnt):
            e = (start + k) % 64
            o = 352 + e * 6
            if w[o] != 2:
                continue
            t0, t1 = w[o + 2] & 0xFFFF, w[o + 2] >> 16
            tbase, toff = w[o + 3] & 0xFFFF, w[o + 3] >> 16
            p = w[o + 4]
            tm, ctx, fn, phase = p & 0xFF, (p >> 8) & 0xFF, (p >> 16) & 0xFF, p >> 24
            print(f"  win=0x{w[o+1]:08X} t0={t0:<5} t1={t1:<5} tbase={tbase:<5} "
                  f"off={toff:<5} tm={tm} ctx={ctx} fn={fn} phase={phase}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
