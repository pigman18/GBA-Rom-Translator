#!/usr/bin/env python3
"""调研(137) 用 GDB 读到的**正确** BG 配置，重新定位字形。

═══════════════════════════════════════════════════════════════════════════
【(136) 的发现：Lua 的 BGxCNT 也是错的】
═══════════════════════════════════════════════════════════════════════════
同一时刻，两种读法得到完全不同的 BG 配置：

                         Lua 读            GDB 读（可信）
  DISPCNT              0x3140            0x5840
  BG0CNT (0x04000008)  0x1E00            0x0700
    charBase           0x0000            0x0000
    screenBase         0xF000            0x3800   ← 完全不同！
  BG3CNT               0x1C0F            0x1F0F

⚠ 但注意：这两个不是同一时刻！Lua 那次是菜单（dc=0x3140），
   GDB 这次是标题（dc=0x5840）。所以 BG 配置不同是正常的。

**真正的关键差异在 VCOUNT：**
   GDB 读 0x06 = 0x00B7（合法 183）
   Lua 读 0x06 = 0x00A0（也合法 160）
   ⇒ 两者在 0x06 都对！之前我看到 `Lua 0x04=0x9629` 才误判。

  所以：**Lua 在 0x00..0x0F 是正确的**，问题只在 0x10 之后
  （HOFS/VOFS/DMA 区读到 0x1C18 填充）。

【那么之前的 BG 分析其实是可信的】
 除了 0x10 之后的 HOFS/VOFS/DMA 不可信，0x00..0x0F 可信。
 即：DISPCNT、DISPSTAT、VCOUNT、BG0-3CNT 都是对的。

【本脚本：既然 IO 基本可信，问题回到「字库在哪」】
 用 GDB 做**真正的执行追踪**：
  在 GBA 的「写入 VRAM」指令上打断点。做法：
  ① 先跑游戏到菜单
  ② 用 GDB 读 VRAM 某个已知字形 tile 的地址
  ③ 在该地址上下**硬件写断点**（mGBA 支持 watchpoint?）
  ④ 若支持，写入时中断 → 立刻知道谁写的

 若不支持 watchpoint，退而求其次：
  ⑤ 单步执行若干帧，记录所有「写 VRAM」的 PC

⚠ 关键：mGBA 的 GDB stub 是否支持 watchpoint，需要测。

用法：python scripts/research/firered/137_gdb_watchpoint.py
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

OUT = ROOT / "work" / "_probe" / "watch"
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

        print("① 测试 GDB stub 支持的断点类型")
        # qSupported 看支持什么
        try:
            sup = c.cmd("qSupported:swbreak+;hwbreak+;watchpoint+")
            print(f"  qSupported 回应：{sup[:300]}")
        except GdbError as e:
            print(f"  失败：{e}")

        # 测 watchpoint
        print("\n② 测试 watchpoint（Z2 = 写断点）")
        for ztype, name in (("2", "write watch"), ("3", "read watch"),
                            ("4", "access watch")):
            try:
                r = c.cmd(f"Z{ztype},06001000,2")
                ok = r.startswith("OK")
                print(f"  Z{ztype} ({name}): {r[:40]}  "
                      f"{'✓ 支持' if ok else '✗'}")
                if ok:
                    c.cmd(f"z{ztype},06001000,2")
            except GdbError as e:
                print(f"  Z{ztype} ({name}): 异常 {e}")

        # 测硬件断点
        print("\n③ 测试硬件断点（Z1）")
        try:
            r = c.cmd("Z1,08FE4814,2")
            print(f"  Z1: {r[:40]}")
            if r.startswith("OK"):
                c.cmd("z1,08FE4814,2")
        except GdbError as e:
            print(f"  Z1 异常: {e}")

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
