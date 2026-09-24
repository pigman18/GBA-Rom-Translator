#!/usr/bin/env python3
"""实验5：ss6 加载后，验证 (1) I/O 读取是否正常 (2) 按键注入是否真的改到 gMain。

只做这两件事，跑 12 秒。
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


def h(g, a, n):
    try:
        return g.read_mem(a, n)
    except GdbError as e:
        return f"ERR {e}"


def main():
    fo = open(os.path.join(ROOT, ".tmp", "t_ss2.out"), "wb")
    p = subprocess.Popen([EXE, "-g", "-t", SS, ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    time.sleep(5)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()

    print("=== 1) I/O 读取（不同长度/地址）===", flush=True)
    for a, n in ((0x04000000, 2), (0x04000000, 1), (0x04000130, 2),
                 (0x03000000, 2), (0x030016E0, 4), (0x08000000, 4)):
        r = h(g, a, n)
        print(f"  read 0x{a:08X},{n} → {r.hex() if isinstance(r, bytes) else r}",
              flush=True)

    print("\n=== 2) 挂 RK 断点，注入 DOWN 并读 gMain ===", flush=True)
    g.set_sw_break(BP_RK)
    got = 0
    for i in range(60):
        try:
            g.cont(timeout=0.15)
        except GdbError:
            pass
        try:
            regs = g.read_regs()
        except GdbError:
            continue
        if (regs.get("r15", 0) & ~1) == BP_RK:
            got += 1
            if i < 8 or i % 15 == 0:
                gm = h(g, GMAIN, 0x30)
                if isinstance(gm, bytes):
                    print(f"  hit{i}: r2=0x{regs.get('r2',0):08X}"
                          f" r3=0x{regs.get('r3',0):04X}"
                          f" gMain.heldKeysRaw=0x{int.from_bytes(gm[0x28:0x2A],'little'):04X}"
                          f" heldKeys=0x{int.from_bytes(gm[0x2C:0x2E],'little'):04X}"
                          f" newKeys=0x{int.from_bytes(gm[0x2E:0x30],'little'):04X}",
                          flush=True)
            # 注入 DOWN
            try:
                g.cmd("P3=" + (0x0080).to_bytes(4, "little").hex())
            except GdbError:
                pass
    print(f"  RK 命中 {got} 次", flush=True)

    print("\n=== 3) 注入后 gMain 现场 ===", flush=True)
    gm = h(g, GMAIN, 0x38)
    if isinstance(gm, bytes):
        print(f"  callback1=0x{int.from_bytes(gm[0:4],'little'):08X}"
              f" callback2=0x{int.from_bytes(gm[4:8],'little'):08X}", flush=True)
        print(f"  heldKeysRaw=0x{int.from_bytes(gm[0x28:0x2A],'little'):04X}"
              f" heldKeys=0x{int.from_bytes(gm[0x2C:0x2E],'little'):04X}"
              f" newKeys=0x{int.from_bytes(gm[0x2E:0x30],'little'):04X}", flush=True)
    else:
        print("  ERR", gm, flush=True)

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
