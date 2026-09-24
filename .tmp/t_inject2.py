#!/usr/bin/env python3
"""可靠按键注入 v2 —— 在 ReadKeys 断点处同时改 held 与 new。

反汇编 0x0800042C (ReadKeys) 实证：
  8000430  ldrh r1,[r0]        ; r1 = REG_KEYINPUT = 0x03FF（空闲，0=按下）
  8000432  ldr  r2,[pc,#56]    ; r2 = 0x030016E0 = gMain
  8000434  adds r0,r2,#0
  8000436  adds r3,r0,#0
  8000438  eors r3,r1          ; ★ r3 = 0x03FF ^ keyinput = 「按下的键」(0=没按)
  800043c  ldrh r2,[r1,#0x28]  ; r2 = gMain.heldKeysRaw  ← ★ 上一帧的值！
  800043e  adds r0,r3,#0
  8000440  bics r0,r2          ; ★ r0 = r3 & ~heldKeysRaw = newKeys
  8000442  strh r0,[r1,#0x2a]  ; newKeysRaw = r0
  8000444  strh r0,[r1,#0x2e]  ; newKeys    = r0
  8000446  strh r0,[r1,#0x30]  ; newAndRepeatedKeys = r0
  ...
  800047e  strh r3,[r2,#0x28]  ; ★ heldKeysRaw = r3   ← 旧断点在这（太晚！）
  8000480  strh r3,[r2,#0x2c]  ; heldKeys    = r3

⇒ 旧方案只在 0x47E 改 r3（heldKeys），但 newKeys 早在 0x442 就算完了
  ⇒ newKeys 恒 = 0 & ~0 = 0 ⇒ 游戏永远收不到「刚按下」！

新方案：断点改到 0x0800043E（算 newKeys 之前），同时改：
  r3 = key   （heldKeys，按键的「按位」表示，0=没按；按下 A ⇒ r3 的 bit0=1）
  r2 = 0     （heldKeysRaw 清 0 ⇒ newKeys = r3 & ~0 = r3）
⇒ newKeys = key ⇒ 游戏当帧收到「刚按下」。
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
OUT = os.path.join(ROOT, ".tmp", "t_inject2.out")

BP = 0x0800043E
GMAIN = 0x030016E0


def main() -> int:
    fo = open(OUT + ".mgba", "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[t2] pid={p.pid}", flush=True)
    time.sleep(4)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    g.set_sw_break(BP)

    def rd(off, n=2):
        try:
            return int.from_bytes(g.read_mem(GMAIN + off, n), "little")
        except GdbError:
            return -1

    print("[t2] 扫命中 0x0800043E ...", flush=True)
    for i in range(600):
        try:
            g.cont(timeout=0.3)
        except GdbError:
            continue
        try:
            regs = g.read_regs()
        except GdbError:
            continue
        if regs.get("r15", 0) & ~1 != BP:
            continue
        print(f"[t2] 命中 #{i}，注入 START(0x0008)", flush=True)
        print(f"     before: heldRaw=0x{rd(0x28):04X} new=0x{rd(0x2E):04X}", flush=True)
        g.cmd("P3=08000000")   # r3 = 0x0008
        g.cmd("P2=00000000")   # r2 = 0（heldKeysRaw 清 0）
        g.cmd("c")
        # 让它跑一小会
        for _ in range(20):
            try:
                g.cont(timeout=0.2)
            except GdbError:
                pass
        try:
            regs = g.read_regs()
        except GdbError:
            pass
        print(f"     after : heldRaw=0x{rd(0x28):04X} new=0x{rd(0x2E):04X}"
              f" held=0x{rd(0x2C):04X}", flush=True)
        print(f"     pc=0x{regs.get('r15',0)&~1:08X}", flush=True)
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
