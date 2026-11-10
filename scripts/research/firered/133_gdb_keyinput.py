#!/usr/bin/env python3
"""调研(133) GDB 里直接写 KEYINPUT 模拟按键 —— 让游戏走到菜单再抓断点。

═══════════════════════════════════════════════════════════════════════════
【(132) 的情况】
═══════════════════════════════════════════════════════════════════════════
GDB 连上了（停因 S02），continue 能跑（20 轮 × 8 秒，全超时 = 游戏在跑），
但断点 0x08FE4814 从未命中 ⇒ 该函数在**冷启动**阶段不被调用。

⇒ 必须让游戏走到菜单。而 continue 是阻塞的，期间没法按键。

【解法：用 GDB 写 KEYINPUT】
 GBA 的按键寄存器 KEYINPUT = 0x04000130（u16，**按下 = 0**）。
 gdb 可以直接写内存：`M addr,2,hhhh`
 ⇒ 在 continue 之前，把 KEYINPUT 写成「按住 A」，游戏就会读到按键。

 时序问题：写的瞬间游戏可能还没读。但 GBA 每帧都读 KEYINPUT，
 只要写进去后游戏跑几帧就会读到。

 实际做法：
   1. 写 KEYINPUT = 0x03FE（按下 A）
   2. cont 短超时（比如 2 秒 = 约 120 帧）
   3. 写 KEYINPUT = 0x03FF（松开）
   4. cont 短超时
   5. 重复 N 次，模拟「反复按 A」
   6. 每次 cont 后检查是否命中断点

 ⚠ gdb 的 cont 在超时后，target 还在跑。用 Ctrl-C（0x03）中断。

【更简单：用 mGBA 的 Lua 按键 + GDB 只读】
 但 Lua 和 GDB 不能同时用（mGBA 只允许一种调试方式）。

⇒ 就用 GDB 写 KEYINPUT。

用法：python scripts/research/firered/133_gdb_keyinput.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "gdbkey"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def write_u16(c: GdbClient, addr: int, val: int) -> bool:
    """用 gdb 的 M 包写 2 字节。"""
    payload = f"M{addr:x},2,{val & 0xFF:02x}{(val >> 8) & 0xFF:02x}"
    try:
        r = c.cmd(payload)
        return r.startswith("OK")
    except GdbError:
        return False


def read_u16(c: GdbClient, addr: int) -> int:
    b = c.read_mem(addr, 2)
    return b[0] | (b[1] << 8)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    mgba = find_mgba()
    print("① 启动 mGBA --gdb")
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(4)

    KEYINPUT = 0x04000130
    A_DOWN = 0x03FE      # bit0 = 0 表示按下 A
    ALL_UP = 0x03FF

    try:
        c = GdbClient("127.0.0.1", 2345, timeout=8.0)
        c.connect()

        # 先确认能写 KEYINPUT
        print("\n② 测试写 KEYINPUT")
        ok = write_u16(c, 0x04000130, A_DOWN)
        print(f"  写 A_DOWN: {'OK' if ok else 'FAIL'}")
        time.sleep(0.1)
        v = read_u16(c, 0x04000130)
        print(f"  读回 0x{v:04X}  {'（值被游戏改回=正常）' if v != A_DOWN else '（保持）'}")
        write_u16(c, KEYINPUT, ALL_UP)

        # 下断点
        print("\n③ 下断点 + 反复按 A")
        c.set_sw_break(0x08FE4814, kind=2)

        hit = False
        for round_ in range(40):
            # 按 A
            write_u16(c, KEYINPUT, A_DOWN)
            try:
                why = c.cont(timeout=0.6)      # 短跑，制造「按住 A 若干帧」
                # 命中了
                print(f"  [轮{round_}] 停机 signal={why}  ← 可能命中！")
                regs = c.cmd("g")
                raw = bytes.fromhex(regs)

                def reg(n):
                    return int.from_bytes(raw[n * 4:(n + 1) * 4], "little")
                pc, lr, sp = reg(15), reg(14), reg(13)
                print(f"    PC=0x{pc:08X} LR=0x{lr:08X} SP=0x{sp:08X}")
                if pc == 0x08FE4814:
                    hit = True
                    print(f"    ★★★ 命中断点！调用者 LR=0x{lr:08X}")
                    r0 = reg(0)
                    print(f"    r0=0x{r0:08X}")
                    stk = c.read_mem(sp, 80)
                    print(f"    栈：")
                    for k in range(0, 80, 4):
                        a = int.from_bytes(stk[k:k + 4], "little")
                        tag = " ← ROM" if 0x08000000 <= a < 0x0A000000 else ""
                        print(f"      [sp+{k:>2}] 0x{a:08X}{tag}")
                    break
            except GdbError:
                pass       # 超时 = 没命中，正常

            # 松开 A
            write_u16(c, KEYINPUT, ALL_UP)
            try:
                c.cont(timeout=0.4)
            except GdbError:
                pass
            write_u16(c, KEYINPUT, 0x03F7)     # START 也试
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            write_u16(c, KEYINPUT, ALL_UP)

            if round_ % 5 == 0:
                print(f"  [轮{round_}] 继续…")

        c.close()
        print(f"\n④ {'命中' if hit else '未命中'}")

    except GdbError as e:
        print(f"GDB 错误：{e}")
    finally:
        try:
            m.terminate(); m.wait(timeout=5)
        except Exception:
            m.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
