#!/usr/bin/env python3
"""调研(130) 用 GDB 在 VRAM 写入点打断点，抓调用栈 —— 真正追打印入口。

═══════════════════════════════════════════════════════════════════════════
【用户说的对：我应该抓执行路径，而不是继续搜数据】
═══════════════════════════════════════════════════════════════════════════
我有：bot（能跑游戏）、mGBA（有 --gdb）、arm-none-eabi-gdb。
前面 30 多个脚本全在**翻 ROM 数据**，从没抓过**运行时执行路径**。

【要做什么】
 1. mGBA 以 --gdb 启动（监听 2345）
 2. gdb 连上，在「字形搬运函数」0x08FE4814 下断点
 3. 命中后打印：寄存器、调用栈、源指针、目标地址
 4. 从而知道：
    · 谁调用它（打印入口）
    · 它从哪个地址读字形
    · 那个地址对应 ROM 哪里

【风险】
 GDB stub 会暂停模拟器，游戏不再前进。
 所以策略是：连上 → 下断点 → continue → 等命中 → 抓信息 → 退出。
 若游戏在断点前需要按键推进，得先让 bot 把游戏走到菜单。

 简化：**先不按键，直接看冷启动时会不会命中**。
       若命中，说明启动就装了字形，那更容易。

用法：python scripts/research/firered/130_gdb_trace.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "gdbtrace"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


GDB_SCRIPT = r"""
set pagination off
set confirm off
set architecture arm
target remote localhost:2345

# 断点：字形搬运函数
break *0x08FE4814
# 也断在可能的字形源（0x08FE4660 被读）
rbreak 0x08FE4814

info registers
continue

# 命中后
info registers
echo \n=== HIT ===\n
bt
x/8i $pc-8
info registers r0 r1 r2 r3 r4 r5 r6 r7
echo \n=== STACK ===\n
x/32wx $sp
echo \n=== END ===\n
detach
quit
"""


def main() -> int:
    mgba = find_mgba()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()

    # 准备 ROM + 存档
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    gdb_script = OUT / "trace.gdb"
    gdb_script.write_text(GDB_SCRIPT, encoding="utf-8")

    print(f"① 启动 mGBA（--gdb，端口 2345）")
    env = dict(os.environ)
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), env=env,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(4)

    print(f"② 用 gdb 连上并下断点")
    gdb_out = OUT / "gdb.log"
    try:
        with open(gdb_out, "w", encoding="utf-8") as f:
            g = subprocess.run(
                ["arm-none-eabi-gdb", "-batch", "-x", str(gdb_script)],
                cwd=str(OUT), stdout=f, stderr=subprocess.STDOUT,
                timeout=120)
        print(f"  gdb 退出码 {g.returncode}")
    except subprocess.TimeoutExpired:
        print("  **gdb 超时（断点可能没命中，游戏没走到那段代码）**")
    finally:
        try:
            m.terminate()
            m.wait(timeout=5)
        except Exception:
            m.kill()

    print(f"\n③ gdb 输出：")
    txt = gdb_out.read_text(encoding="utf-8", errors="replace") \
        if gdb_out.exists() else ""
    print(txt[-4000:] if txt else "（空）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
