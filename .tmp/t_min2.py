#!/usr/bin/env python3
"""最小诊断 —— 断点命中数 + gMain 可读性 + pc 落点分布。

不做按键、不做逻辑。纯粹问三个问题：
  Q1: BP 0x0800043E 在 10 秒内命中几次？
  Q2: gMain (0x030016E0) 能读吗？内容是什么？
  Q3: pc 落点集中在哪几个区间？
"""
from __future__ import annotations

import collections
import os
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
OUT = os.path.join(ROOT, ".tmp", "t_min2.out")

BPS = [0x0800043E, 0x0800047E, 0x08003630, 0x08002A50]


def main() -> int:
    fo = open(OUT + ".mgba", "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[m] pid={p.pid}", flush=True)
    time.sleep(4)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()

    print("=== Q2: gMain 可读性 ===", flush=True)
    for base in (0x030016E0, 0x03000328):
        try:
            d = g.read_mem(base, 0x40)
            print(f"  @0x{base:08X} ({len(d)}B) {d[:32].hex(' ')}", flush=True)
        except GdbError as e:
            print(f"  @0x{base:08X} 读失败: {e}", flush=True)

    print("=== Q1: 设 4 个断点，跑 10 秒 ===", flush=True)
    for a in BPS:
        try:
            g.set_sw_break(a)
        except GdbError as e:
            print(f"  设断失败 0x{a:08X}: {e}", flush=True)
    hc = collections.Counter()
    pc_bands = collections.Counter()
    end = time.time() + 10.0
    n = 0
    while time.time() < end:
        try:
            g.cont(timeout=0.25)
        except GdbError:
            pass
        try:
            regs = g.read_regs()
        except GdbError:
            continue
        pc = regs.get("r15", 0) & ~1
        n += 1
        if pc in BPS:
            hc[pc] += 1
        pc_bands[f"0x{pc & 0xFF000000:08X}"] += 1
    print(f"  采样 {n} 次", flush=True)
    print("  断点命中:", flush=True)
    for a in BPS:
        print(f"    0x{a:08X}  ×{hc[a]}", flush=True)
    print("  pc 高位分布:", flush=True)
    for k, v in pc_bands.most_common(10):
        print(f"    {k}  ×{v}", flush=True)

    print("=== Q3: 再读 gMain（跑过之后）===", flush=True)
    try:
        d = g.read_mem(0x030016E0, 0x40)
        print(f"  {d[:32].hex(' ')}", flush=True)
    except GdbError as e:
        print(f"  失败: {e}", flush=True)

    for a in BPS:
        try:
            g.clear_sw_break(a)
        except GdbError:
            pass
    g.close()
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()
    fo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
