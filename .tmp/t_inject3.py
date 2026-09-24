#!/usr/bin/env python3
"""可靠按键注入 v3 —— 断点只用来「抓住一帧」，写完寄存器立刻摘断点。

关键教训（t_inject2 血案）：
  在断点处 g.cmd("c") 会立刻被同一个断点再次命中 ⇒ 游戏根本没跑。
  必须：抓住 → 写寄存器 → **摘断点** → cont 跑起来。

正确流程（每拍）：
  1. set_sw_break(BP)
  2. cont 直到命中 BP
  3. P3=key  P2=0     ← 改 held 与 heldKeysRaw
  4. clear_sw_break(BP)
  5. cont(0.12)       ← 跑掉这一帧（此时 ReadKeys 会把 newKeys 写进 gMain）
  6. 回到 1

另：ReadKeys 每帧都被调 ⇒ 每帧都要重新抓一次。
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
OUT = os.path.join(ROOT, ".tmp", "t_inject3.out")

BP = 0x0800043E
GMAIN = 0x030016E0


def main() -> int:
    fo = open(OUT + ".mgba", "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[t3] pid={p.pid}", flush=True)
    time.sleep(4)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()

    def rd(off, n=2):
        try:
            return int.from_bytes(g.read_mem(GMAIN + off, n), "little")
        except GdbError:
            return -1

    def grab_frame():
        """抓一帧 ReadKeys，返回是否命中。断点留着。"""
        g.set_sw_break(BP)
        for _ in range(30):
            try:
                g.cont(timeout=0.15)
            except GdbError:
                pass
            try:
                regs = g.read_regs()
            except GdbError:
                continue
            if regs.get("r15", 0) & ~1 == BP:
                return True
        return False

    def release():
        try:
            g.clear_sw_break(BP)
        except GdbError:
            pass

    def run(t):
        end = time.time() + t
        while time.time() < end:
            try:
                g.cont(timeout=0.2)
            except GdbError:
                pass

    # 先让游戏跑 6s 到标题
    run(6.0)
    print(f"[t3] 启动后 heldRaw=0x{rd(0x28):04X}", flush=True)

    # 注入 START：3 拍按下 + 3 拍松开
    for i, k in enumerate([0x0008, 0x0008, 0x0008, 0, 0, 0]):
        if not grab_frame():
            print(f"[t3] 第{i}拍未抓到帧", flush=True)
            continue
        g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
        g.cmd("P2=00000000")
        release()
        run(0.10)
        print(f"[t3] 拍{i} 注入 0x{k:04X} ⇒ heldRaw=0x{rd(0x28):04X}"
              f" new=0x{rd(0x2E):04X} held=0x{rd(0x2C):04X}", flush=True)

    run(2.0)
    print(f"[t3] 收尾 pc=0x{g.read_regs().get('r15',0)&~1:08X}", flush=True)

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
