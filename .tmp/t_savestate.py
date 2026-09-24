#!/usr/bin/env python3
"""实验4：加载 savestate 直接进游戏内，确认哪种 ss 是「游戏内」状态。

判据：加载后读
  · gMain@0x030016E0 的 callback1/callback2（非 0 = 真实场景）
  · DISPCNT
  · 挂 DGT/IWTD/GCTN 断点跑 4 秒，看命中分布
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
GMAIN = 0x030016E0

BP_DGT = 0x08003630
BP_IWTD = 0x08002A50
BP_GCTN = 0x08003708


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little")


def probe(tag, state_file=None):
    args = [EXE, "-g"]
    if state_file:
        args += ["-t", state_file]
    args.append(ROM)
    fo = open(os.path.join(ROOT, ".tmp", "t_ss.out"), "wb")
    p = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL,
                         stdout=fo, stderr=fo)
    time.sleep(4)
    try:
        g = GdbClient("127.0.0.1", 2345, timeout=6.0)
        g.connect()
    except Exception as e:
        print(f"  [{tag}] 连接失败: {e}", flush=True)
        p.terminate(); fo.close(); return
    for a in (BP_DGT, BP_IWTD, BP_GCTN):
        try:
            g.set_sw_break(a)
        except GdbError:
            pass
    gm = g.read_mem(GMAIN, 0x20)
    disc = u32(g.read_mem(0x04000000, 2), 0)
    print(f"\n[{tag}] {os.path.basename(state_file) if state_file else '无savestate'}",
          flush=True)
    print(f"  gMain.callback1=0x{u32(gm,0):08X} callback2=0x{u32(gm,4):08X}"
          f" savedCallback=0x{u32(gm,8):08X}", flush=True)
    print(f"  DISPCNT=0x{disc:04X} heldKeys=0x{int.from_bytes(g.read_mem(GMAIN+0x2C,2),'little'):04X}",
          flush=True)
    cnt = {"DGT": 0, "IWTD": 0, "GCTN": 0}
    end = time.time() + 4
    while time.time() < end:
        try:
            g.cont(timeout=0.25)
        except GdbError:
            pass
        try:
            pc = g.read_regs().get("r15", 0) & ~1
        except GdbError:
            continue
        if pc == BP_DGT:
            cnt["DGT"] += 1
        elif pc == BP_IWTD:
            cnt["IWTD"] += 1
        elif pc == BP_GCTN:
            cnt["GCTN"] += 1
    print(f"  4s 命中: {cnt}", flush=True)
    g.close()
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()
    fo.close()
    time.sleep(1.5)


def main():
    outputs = os.path.join(ROOT, "roms", "outputs")
    for n in ("ss6", "ss5", "ss4"):
        f = os.path.join(outputs, f"POKEMON_RUBY_AXVJ00_translated.{n}")
        if os.path.isfile(f):
            probe(n, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
