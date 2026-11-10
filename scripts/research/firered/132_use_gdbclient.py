#!/usr/bin/env python3
"""调研(132) 用项目现成的 GdbClient 抓「字形从哪读」—— 不再自己拼 gdb 脚本。

═══════════════════════════════════════════════════════════════════════════
【为什么之前失败】
═══════════════════════════════════════════════════════════════════════════
我自己写 `arm-none-eabi-gdb -batch -x 脚本`，问题：
  · mGBA 的 GDB stub **只接受一次连接**（用户的提醒）
  · `-batch` 模式下 gdb 退出就断开了，没法分段操作
  · 无法「先跑起来、按键、再下断点」

【项目已有正确工具】
  src/util/debug_patcher.py 里的 `GdbClient`：
    · connect()            连一次
    · set_sw_break(addr)   Thumb 软件断点
    · cont(timeout)        continue 并等停
    · read_mem(addr, len)  直接读内存
  它保持长连接，可以反复设置断点 / continue。

  src/util/gdb_patcher.py 已用它做「监听点」式追踪。

【本脚本做法】
 1. mGBA 以 --gdb 启动（暂停在复位）
 2. GdbClient 连接（只有这一次）
 3. 设断点：字形搬运函数 0x08FE4814
 4. cont 循环，命中后打印 PC/LR/r0-r5 与栈
 5. 从 r0/r1 看出「源数据地址」和「VRAM 目标」

 ⚠ 关键：游戏需要按键才能走到菜单。
    做法：先不放断点，让游戏跑一段（cont 带超时，超时算正常），
          期间用 mGBA 的 Lua 侧按键？不行，Lua 和 gdb 不能同时。

    替代：**先读档**。用 .sav 让游戏启动时自动进？火红需要按键选「继续游戏」。

    最实际：设断点后 cont，**手动用 mGBA 窗口按键**（我这边发虚拟按键）。
    或者：接受「冷启动也能命中」—— 若字形在标题画面就加载，那就能抓到。

用法：python scripts/research/firered/132_use_gdbclient.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "gdbtrace3"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
BASE = 0x08000000


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
    print(f"① 启动 mGBA --gdb")
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(4)

    try:
        print(f"② GdbClient 连接（唯一一次）")
        c = GdbClient("127.0.0.1", 2345, timeout=10.0)
        c.connect()

        # 读当前 PC，确认在复位
        print(f"\n③ 当前状态")
        regs = c.cmd("g")
        if regs and not regs.startswith("E"):
            # ARM 寄存器组：r0-r15 + cpsr 共 16*4 + 4 = 68 字节 hex? 
            # gdb 的 g 包返回 r0..r15, cpsr(可能 25 个寄存器)
            raw = bytes.fromhex(regs)
            print(f"  g 包长度 {len(raw)} 字节 = {len(raw)//4} 个寄存器")
            pc = int.from_bytes(raw[15 * 4:16 * 4], "little") if len(raw) >= 64 else 0
            print(f"  PC = 0x{pc:08X}")

        # 设断点
        print(f"\n④ 设断点：字形搬运函数 0x08FE4814")
        c.set_sw_break(0x08FE4814, kind=2)
        c.cmd("z1,0x08FE4814,2")     # 先删掉再重设，确保干净
        c.set_sw_break(0x08FE4814, kind=2)
        print(f"  已设")

        # continue，等命中（多轮）
        print(f"\n⑤ continue，等断点（每轮 8 秒，最多 20 轮）")
        hits = 0
        for i in range(20):
            try:
                why = c.cont(timeout=8.0)
                print(f"  [轮{i}] 停机，信号={why}")
                # 读寄存器
                regs = c.cmd("g")
                raw = bytes.fromhex(regs)
                def reg(n):
                    return int.from_bytes(raw[n * 4:(n + 1) * 4], "little")
                pc = reg(15)
                lr = reg(14)
                sp = reg(13)
                r0, r1, r2, r3 = reg(0), reg(1), reg(2), reg(3)
                print(f"    PC=0x{pc:08X} LR=0x{lr:08X} SP=0x{sp:08X}")
                print(f"    r0=0x{r0:08X} r1=0x{r1:08X} "
                      f"r2=0x{r2:08X} r3=0x{r3:08X}")
                if pc == 0x08FE4814:
                    hits += 1
                    print(f"    ★ 命中字形搬运函数！")
                    print(f"      r0（源偏移/数据）= 0x{r0:08X}")
                    # 读栈，找返回地址（= 调用者）
                    stk = c.read_mem(sp, 64)
                    addrs = [int.from_bytes(stk[k:k + 4], "little")
                             for k in range(0, 64, 4)]
                    print(f"      栈顶 16 个 u32：")
                    for k, a in enumerate(addrs):
                        tag = ""
                        if 0x08000000 <= a < 0x0A000000:
                            tag = " ← ROM 代码/数据"
                        print(f"        [sp+{k*4:>2}] 0x{a:08X}{tag}")
                    break
                else:
                    # 不是目标断点，继续
                    if i >= 5:
                        print(f"    （非目标断点，继续）")
                        continue
            except GdbError as e:
                print(f"  [轮{i}] {e}")
                # 超时 = 没命中，继续试
                continue

        c.close()
        print(f"\n⑥ 命中 {hits} 次")

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
