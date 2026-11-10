#!/usr/bin/env python3
"""调研(150) 修 g 包解析：mGBA 的 g 包返回 25 个寄存器（ARM 态），不是 17。

═══════════════════════════════════════════════════════════════════════════
【(149) 的问题】
═══════════════════════════════════════════════════════════════════════════
命中 70 次，但 **PC 全是 0x00000000**，说明寄存器解析错了。

原因：GDB 的 `g` 包长度取决于是 ARM 态还是 Thumb 态：
  · ARM 态：r0-r15 + cpsr + 额外 8 个（f0-f7 或 s0-s31）→ 26 个 32 位 = 104 字节
  · Thumb 态：同样寄存器数

(136) 实测 `g` 包长度 = **68 字节 = 17 个寄存器**。
但 (149) 我截取 `[:68]`，而 PC 在索引 15 → 偏移 60..64。68 字节够。
问题在别处：`raw[60:64]` 应该是 PC，但读到 0。

⇒ 可能 `g` 包开头不是 r0 而是别的布局，或者我抓到了错误的响应。

【正确做法：用 GDB 的 `p` 命令直接读 PC】
 gdb stub 支持 `p n` 读单个寄存器？不一定。
 但支持读内存 `m`，而 PC 可以从 `?` 或 `T` 包的回应里取。

 更可靠：**用 `T05watch:xxx;` 这种 stop reply 里的寄存器信息**，
 或者先用 `m` 读栈，再从 LR 推断。

【最稳妥：用 objdump 式的「按 PC 反汇编」代替寄存器解析】
 既然要看「谁写 VRAM」，可以：
  ① 命中时读 LR（返回地址），LR 一定指向调用者
  ② 直接在 ROM 里反汇编 LR 附近的代码

【本脚本：改测 g 包的真实布局】
 ① 连接后先跑一段，让 PC 落在已知代码区
 ② 打印完整的 g 包前 128 字节，标出哪个偏移是 PC
 ③ 用已知值交叉验证（比如当前 PC 应该在 ROM 内）

用法：python scripts/research/firered/150_fix_gpak.py
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bot"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402
from winhide import popen_hidden                     # noqa: E402

OUT = ROOT / "work" / "_probe" / "gpak"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba() -> Path:
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
    proc = popen_hidden([str(mgba), "--gdb", str(rom_copy)],
                        cwd=str(OUT))
    time.sleep(5)

    try:
        c = GdbClient("127.0.0.1", 2345, timeout=15.0)
        c.connect()

        print("① continue 让游戏跑 3 秒")
        try:
            c.cont(timeout=3.0)
        except GdbError:
            pass

        print("\n② 读 g 包，看长度和布局")
        for trial in range(3):
            try:
                c.cont(timeout=1.0)
            except GdbError:
                pass
            g = c.cmd("g")
            hp = "".join(ch for ch in g
                         if ch in "0123456789abcdefABCDEF")
            print(f"\n  [试 {trial}] g 包总长 {len(g)}，hex 部分 {len(hp)} 字符")
            print(f"    原始前 120 字符: {g[:120]}")

            n_reg = len(hp) // 8
            print(f"    推得寄存器数 {n_reg}")
            if n_reg >= 15:
                vals = [int(hp[k * 8:(k + 1) * 8], 16)
                        for k in range(n_reg)]
                # 反转字节序（gdb 是大端 hex 表示寄存器值）
                vals_le = [int.from_bytes(
                    bytes.fromhex(hp[k * 8:(k + 1) * 8]), "big")
                    for k in range(n_reg)]
                print(f"    前 16 个值（大端解释）:")
                for k in range(min(16, n_reg)):
                    v = vals_le[k]
                    tag = ""
                    if 0x08000000 <= v < 0x0A000000:
                        tag = " ← ROM"
                    elif 0x02000000 <= v < 0x03000000:
                        tag = " ← EWRAM"
                    elif 0x03000000 <= v < 0x03008000:
                        tag = " ← IWRAM"
                    elif 0x06000000 <= v < 0x07000000:
                        tag = " ← VRAM"
                    print(f"      r{k:<2} = 0x{v:08X}{tag}")

        c.close()
    except GdbError as e:
        print(f"GDB 错误：{e}")
    finally:
        try:
            proc.terminate(); proc.wait(timeout=5)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
