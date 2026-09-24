#!/usr/bin/env python3
"""验证 P3= 到底能不能改寄存器 —— 最小实验。

在 ReadKeys 的 0x0800047E 下断点，读回 r3，写 r3=0xDEADBEEF，再读回。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
OUT = os.path.join(ROOT, ".tmp", "t_p3.out")

BP = 0x0800047E
GMAIN = 0x030016E0


def main() -> int:
    fo = open(OUT + ".mgba", "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[t] pid={p.pid}", flush=True)
    time.sleep(4)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    g.set_sw_break(BP)
    print("[t] BP 0x0800047E 已设，扫命中...", flush=True)

    hit = 0
    for i in range(400):
        try:
            g.cont(timeout=0.3)
        except GdbError:
            continue
        try:
            regs = g.read_regs()
        except GdbError:
            continue
        pc = regs.get("r15", 0) & ~1
        if pc != BP:
            continue
        hit += 1
        if hit > 4:
            break
        r2 = regs.get("r2", 0)
        r3_before = regs.get("r3", 0)
        print(f"[t] hit#{hit} pc=0x{pc:08X} r2=0x{r2:08X} r3=0x{r3_before:08X}", flush=True)

        # 读 before
        hb = g.read_mem(GMAIN + 0x28, 2)
        print(f"    heldRaw before = 0x{int.from_bytes(hb,'little'):04X}", flush=True)

        # 写 r3 = 0x0001 (A)
        g.cmd("P3=01000000")
        regs2 = g.read_regs()
        print(f"    写后读回 r3 = 0x{regs2.get('r3',0):08X}  "
              f"(期望 0x00000001)", flush=True)

        # 单步执行 strh，然后读 heldRaw
        try:
            g.cmd("s")
            regs3 = g.read_regs()
            print(f"    single-step 后 pc=0x{regs3.get('r15',0)&~1:08X}", flush=True)
        except GdbError as e:
            print(f"    single-step 失败: {e}", flush=True)

        ha = g.read_mem(GMAIN + 0x28, 2)
        print(f"    heldRaw after  = 0x{int.from_bytes(ha,'little'):04X}  "
              f"(期望 0x0001)", flush=True)
        break

    g.clear_sw_break(BP)
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
