#!/usr/bin/env python3
"""调研(131) GDB 完整流程：先跑起来读档，再下断点抓字形加载。

═══════════════════════════════════════════════════════════════════════════
【(130) 的问题】
═══════════════════════════════════════════════════════════════════════════
gdb 连上后 `pc=0x0`、断点没命中、超时。
原因：`--gdb` 启动时模拟器**暂停在复位向量**，我 `continue` 后
      只等到断点，但游戏需要按键才能走到菜单，没人按键 ⇒ 永远不进菜单。

【正确流程】
 1. mGBA --gdb 启动（暂停在 0x0）
 2. gdb 连上，`continue` 让游戏跑
 3. **同时**用 Python 往 mGBA 窗口发按键（或者让 bot 驱动）
 4. 等游戏到菜单
 5. gdb 用 Ctrl-C 中断，下断点，`continue`
 6. 断点命中 → 抓调用栈

⚠ 难点：gdb 的 `continue` 是阻塞的，没法边跑边按键。

【替代方案：用「监视点」直接抓 VRAM 写入】
 GBA 的字形最终会被写进 VRAM。用**硬件断点**（watchpoint）监视
 VRAM 里某个字形位置，写入时中断 —— 立刻就知道是谁写的。

 但 GBA 只有 2 个硬件断点，且 mGBA 的 stub 未必支持 watchpoint。

【更简单的替代：在「读取 ROM 字库」的位置下断】
 若字形从 ROM 读，那么读取时一定经过某段代码。
 用 gdb 的 `rwatch` 监视一个「疑似字库地址」…

【本脚本采用最实用的方案：分段执行 + 中间注入按键】
 gdb 脚本里用 `continue` 带超时，配合外部按键。
 具体做法：让 mGBA 不暂停（不用 --gdb，改用 bot 跑），
          但用 gdb 在**后期**连上（mGBA 支持运行中连接 gdb 吗？）

实测：mGBA 的 --gdb 只在启动时监听。
⇒ 改用另一个思路：**不给断点，直接单步跟踪**。

【最终采用：抓「谁访问了 VRAM 的某个 tile 地址」】
 ① 先跑一遍拿到「菜单画面 VRAM 里某个字形 tile 的地址」
 ② 重开一局，在**写该地址的指令**上下断点
 ③ 但要先知道写指令地址…

这就是循环依赖。

【破局：从已知的 VRAM 写入代码反推】
 (107) 已知：汉化没有新增 0x06000000 引用，所以写 VRAM 走**原版代码**。
 原版代码里，0x06000000 的引用有 70 处。
 ⇒ 逐个在这 70 处下断点，看哪个在菜单出现时被命中。

用法：python scripts/research/firered/131_gdb_all_vram_writers.py
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "gdbtrace2"
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


def vram_refs(zh: bytes) -> list[int]:
    """找所有引用 0x06000000 的代码位置。"""
    m = len(zh) // 4 * 4
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)
    hit = np.flatnonzero(pz == 0x06000000)
    return [int(h) * 4 + BASE for h in hit]


def main() -> int:
    zh = ROM.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()

    refs = vram_refs(zh)
    print(f"① 找到 {len(refs)} 处引用 0x06000000")
    for r in refs[:10]:
        print(f"    字面量 @0x{r:08X}")

    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    # 策略：在**字面量所在函数**下断点太宽。
    # 改为：断点设在「字形搬运函数 0x08FE4814」+「若干 VRAM 字面量前 0x20 处」
    bps = [0x08FE4814]
    # 取前 8 个 VRAM 字面量，断在它们「前面」（可能是 ldr 使用点）
    for r in refs[:8]:
        cand = r - 0x10
        if 0x08000000 <= cand < 0x0A000000:
            bps.append(cand)

    gdb_lines = [
        "set pagination off",
        "set confirm off",
        "set architecture arm",
        "target remote localhost:2345",
    ]
    for i, a in enumerate(bps, 1):
        gdb_lines.append(f"break *0x{a:08X}")
    gdb_lines += [
        "continue",
        "echo \\n=== HIT ===\\n",
        "info registers pc lr sp",
        "bt",
        "x/6i $pc-8",
        "echo \\n=== STACK ===\\n",
        "x/24wx $sp",
        "quit",
    ]
    gdb_script = OUT / "t.gdb"
    gdb_script.write_text("\n".join(gdb_lines), encoding="utf-8")

    mgba = find_mgba()
    print(f"② 启动 mGBA --gdb")
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(4)

    print(f"③ gdb 下 {len(bps)} 个断点并 continue")
    log = OUT / "gdb.log"
    try:
        with open(log, "w", encoding="utf-8") as f:
            subprocess.run(["arm-none-eabi-gdb", "-batch", "-x",
                            str(gdb_script)],
                           cwd=str(OUT), stdout=f, stderr=subprocess.STDOUT,
                           timeout=90)
    except subprocess.TimeoutExpired:
        print("  超时（断点未命中，说明这些地址在启动阶段没被执行）")
    finally:
        try:
            m.terminate(); m.wait(timeout=5)
        except Exception:
            m.kill()

    print(f"\n④ gdb 输出：")
    txt = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    print(txt[-3000:] if txt else "（空）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
