#!/usr/bin/env python3
"""实验3：验证「断点停在 ReadKeys 的 strh 前 + 改 r3」能否注入按键。

断点 0x0800047E (strh r3,[r2,#0x28])：命中时 r2=gMain基址, r3=本帧按键（未写）。
手段：GDB 'P<reg>=<hex>' 改 r3 → 继续 → 游戏读到我们想要的键。

自证：
  1. 命中后读 r2，应为 0x030016E0（验证 gMain 推断）
  2. 改 r3 为 START，之后读 gMain.newKeys(0x0300170E) 应非 0
  3. 观察 pc 分布是否离开标题画面
"""
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

BP_READKEYS = 0x0800047E   # strh r3,[r2,#0x28]  ← 注入点
GMAIN_EXPECT = 0x030016E0

REG_NUM = {"r0": 0, "r1": 1, "r2": 2, "r3": 3, "r4": 4, "r5": 5, "r6": 6,
           "r7": 7, "r8": 8, "r9": 9, "r10": 10, "r11": 11, "r12": 12,
           "sp": 13, "lr": 14, "pc": 15}

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}


def poke_reg(g, name: str, val: int) -> None:
    n = REG_NUM[name]
    le = (val & 0xFFFFFFFF).to_bytes(4, "little").hex()
    g.cmd(f"P{n:x}={le}")


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "t_inject.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"mGBA pid={p.pid}", flush=True)
    time.sleep(4)

    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()

    g.set_sw_break(BP_READKEYS)
    print(f"断点 0x{BP_READKEYS:08X} 已挂", flush=True)

    # 脚本：前 3 秒不按键（观察 gMain），之后按 START×3, A×3
    hits = 0
    gmain_seen = collections.Counter()
    pcs = collections.Counter()
    KEY_SCRIPT = ([0] * 20 + [KEYS["START"]] * 4 + [0] * 10
                  + [KEYS["START"]] * 4 + [0] * 10
                  + [KEYS["A"]] * 4 + [0] * 10
                  + [KEYS["A"]] * 4 + [0] * 10
                  + [KEYS["A"]] * 4 + [0] * 10)
    si = 0
    t_end = time.time() + 26
    while time.time() < t_end:
        try:
            g.cont(timeout=0.20)
        except GdbError:
            pass
        try:
            regs = g.read_regs()
        except GdbError:
            continue
        pc = regs.get("r15", 0) & ~1
        pcs[f"0x{pc:08X}"] += 1
        if pc == BP_READKEYS:
            hits += 1
            r2 = regs.get("r2", 0)
            gmain_seen[f"0x{r2:08X}"] += 1
            # 注入：用脚本值替换 r3
            want = KEY_SCRIPT[si % len(KEY_SCRIPT)]
            si += 1
            real = regs.get("r3", 0)
            if want:
                try:
                    poke_reg(g, "r3", want)
                except GdbError as e:
                    print(f"  poke r3 失败: {e}", flush=True)
            if hits <= 3 or hits % 200 == 0:
                print(f"  hit#{hits} r2=0x{r2:08X} real_r3=0x{real:04X}"
                      f" → inject=0x{want:04X}", flush=True)
    print(f"\nReadKeys 命中 {hits} 次", flush=True)
    print("r2 值分布:", gmain_seen.most_common(3), flush=True)
    print("pc top8:", pcs.most_common(8), flush=True)

    # 读 gMain 现场
    try:
        gm = g.read_mem(GMAIN_EXPECT, 0x38)
        print(f"\ngMain@0x{GMAIN_EXPECT:08X} 前0x38:", gm.hex(" "), flush=True)
        print(f"  heldKeysRaw=0x{int.from_bytes(gm[0x28:0x2a],'little'):04X}"
              f" newKeysRaw=0x{int.from_bytes(gm[0x2a:0x2c],'little'):04X}"
              f" heldKeys=0x{int.from_bytes(gm[0x2c:0x2e],'little'):04X}"
              f" newKeys=0x{int.from_bytes(gm[0x2e:0x30],'little'):04X}", flush=True)
    except GdbError as e:
        print("读 gMain 失败:", e, flush=True)

    print(f"\nDISPCNT=0x{int.from_bytes(g.read_mem(0x04000000,2),'little'):04X}",
          flush=True)
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
