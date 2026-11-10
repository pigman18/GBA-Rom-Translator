#!/usr/bin/env python3
"""调研(138) 用 watchpoint 抓「谁往 VRAM 写字形」—— 最终手段。

═══════════════════════════════════════════════════════════════════════════
【(137) 确认：mGBA 的 GDB stub 支持 watchpoint】
═══════════════════════════════════════════════════════════════════════════
    Z2 (write watch):  OK
    Z3 (read watch):   OK
    Z4 (access watch): OK
    Z1 (hw breakpoint):OK

⇒ 可以监视「谁写了 VRAM 的某个地址」，这是**直接抓到字形来源**的最强手段。

【难点：怎么让游戏走到菜单】
 continue 是阻塞的，期间没法按键。
 但 mGBA 的 GDB stub 支持 `QStartNoAckMode`，可以加速。

 关键洞察：**GDB 可以写内存**（M 包）。虽然 KEYINPUT 是硬件寄存器，
 但**游戏的按键状态可能缓存在 RAM 里**。

 更简单：**GBA 的 KEYINPUT 可以被「覆盖」吗？** 不行，是只读硬件。

 ⇒ 换方案：**先把游戏跑到菜单，再下 watchpoint**。
    怎么跑到菜单？用 bot 的 Lua 跑一遍（mGBA 正常模式），
    但那样没有 GDB…

 ⭐ 真正的解法：**mGBA 允许运行中启动 GDB stub**（Tools 菜单），
    但命令行 --gdb 是启动时监听，只连一次（用户提醒过）。

 ⇒ 所以必须：**GDB 连接后，用 GDB 驱动游戏前进**。

    GDB 能写内存，但按键是硬件。**除非观察到一个事实：**
    游戏读取按键是通过 ldrh rX,[0x04000130]。
    若我在**该读取指令之后**用 GDB 修改返回的寄存器值…可以！
    但要知道读按键的代码地址。

 ⭐ 最实用的方案：**接受「不按键也能验证」**
    字形数据在**冷启动时也可能被加载**（比如标题画面就有字）。
    标题画面的「PUSH START」等字也要渲染。

 ⇒ 本脚本：
    ① 冷启动，设 watchpoint 监视 VRAM 常见字模区（0x06000000 起）
    ② cont，等 watchpoint 命中
    ③ 命中的 PC 就是「写 VRAM 的代码」
    ④ 从 PC 附近的指令看出「源地址从哪来」

用法：python scripts/research/firered/138_watch_vram_write.py
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "watch2"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    mgba = find_mgba()
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(4)

    try:
        c = GdbClient("127.0.0.1", 2345, timeout=10.0)
        c.connect()

        # 先让游戏跑过 BIOS/启动，进入标题
        print("① 冷启动跑 3 秒")
        try:
            c.cont(timeout=3.0)
        except GdbError:
            pass

        print("② 读当前 DISPCNT / VCOUNT 确认已在游戏里")
        regs = c.cmd("g")
        raw = bytes.fromhex(regs)

        def reg(n):
            return int.from_bytes(raw[n * 4:(n + 1) * 4], "little")
        print(f"  PC = 0x{reg(15):08X}")
        io = c.read_mem(0x04000000, 0x10)
        dc = struct.unpack_from("<H", io, 0)[0]
        vc = struct.unpack_from("<H", io, 6)[0]
        print(f"  DISPCNT = 0x{dc:04X}")
        print(f"  VCOUNT  = 0x{vc:04X}")

        # ── ③ 在 VRAM 字模区设写监视 ────────────────────────
        # BG0 charBase 通常是 0x06000000；监视前 0x1000 字节
        print("\n③ 在 VRAM 0x06000000 设写监视（Z2）")
        targets = [0x06000000, 0x06004000, 0x06008000, 0x0600C000]
        set_ok = []
        for t in targets:
            try:
                r = c.cmd(f"Z2,{t:x},2")
                if r.startswith("OK"):
                    set_ok.append(t)
            except GdbError:
                pass
        print(f"  成功设置 {len(set_ok)} 个 watchpoint: "
              f"{[f'0x{x:08X}' for x in set_ok]}")

        if not set_ok:
            print("  **无法设置 watchpoint**")
            c.close()
            return 1

        # ── ④ cont 等命中 ──────────────────────────────────
        print("\n④ continue 等 watchpoint 命中（最多 15 轮）")
        hits = 0
        for i in range(15):
            try:
                why = c.cont(timeout=2.0)
                print(f"  [轮{i}] 停机 signal={why}")
                regs = c.cmd("g")
                raw = bytes.fromhex(regs)

                def r2(n):
                    return int.from_bytes(raw[n * 4:(n + 1) * 4], "little")
                pc, lr, sp = r2(15), r2(14), r2(13)
                print(f"    PC=0x{pc:08X} LR=0x{lr:08X} SP=0x{sp:08X}")
                print(f"    r0=0x{r2(0):08X} r1=0x{r2(1):08X} "
                      f"r2=0x{r2(2):08X} r3=0x{r2(3):08X}")
                hits += 1

                # 若是 ROM 地址，读出来看
                for n in range(4):
                    v = r2(n)
                    if 0x08000000 <= v < 0x0A000000:
                        try:
                            blob = c.read_mem(v, 32)
                            print(f"      r{n}=ROM 0x{v:08X} → "
                                  f"{blob.hex(' ')}")
                        except GdbError:
                            pass

                if hits >= 5:
                    break
            except GdbError:
                pass    # 超时正常

        print(f"\n⑤ 命中 {hits} 次")
        c.close()
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
