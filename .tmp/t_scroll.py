#!/usr/bin/env python3
"""实验6：用 BG 滚动寄存器验证按键是否真的驱动了游戏。

判据：按住 DOWN 时 REG_BG0VOFS(0x04000012) / BG1VOFS 等应变化。
     静止不动 → 寄存器不变。
"""
import os
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
SS = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.ss6")
GMAIN = 0x030016E0
BP_RK = 0x0800047E

SCROLLS = (0x04000010, 0x04000012, 0x04000014, 0x04000016,
           0x04000018, 0x0400001A)


def rd(g, a, n=2):
    try:
        v = g.read_mem(a, n)
        return int.from_bytes(v, "little") if len(v) == n else -1
    except GdbError:
        return -1


def main():
    fo = open(os.path.join(ROOT, ".tmp", "t_scroll.out"), "wb")
    p = subprocess.Popen([EXE, "-g", "-t", SS, ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    time.sleep(5)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()

    def snap(tag):
        vals = [rd(g, a) for a in SCROLLS]
        print(f"  {tag}: " + " ".join(f"0x{a:06X}={v:04X}"
                                      for a, v in zip(SCROLLS, vals)), flush=True)
        return vals

    print("=== 静止 2s（不按键，看是否本来就静止）===", flush=True)
    for _ in range(4):
        snap("静止")
        time.sleep(0.5)

    print("\n=== 按住 DOWN 3s（每 0.4s 采样）===", flush=True)
    g.set_sw_break(BP_RK)
    end = time.time() + 3
    n = 0
    while time.time() < end:
        try:
            g.cont(timeout=0.12)
        except GdbError:
            pass
        try:
            regs = g.read_regs()
        except GdbError:
            continue
        if (regs.get("r15", 0) & ~1) == BP_RK:
            try:
                g.cmd("P3=" + (0x0080).to_bytes(4, "little").hex())
            except GdbError:
                pass
            n += 1
            if n % 20 == 0:
                snap(f"DOWN({n})")
    print(f"  注入 {n} 拍", flush=True)
    g.clear_sw_break(BP_RK)

    print("\n=== 松开后 2s ===", flush=True)
    for _ in range(4):
        g.cont(timeout=0.3)
        snap("松开")
        time.sleep(0.4)

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
