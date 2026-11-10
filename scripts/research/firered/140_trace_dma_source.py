#!/usr/bin/env python3
"""调研(140) 抓 EWRAM 里的 DMA 源地址 —— 顺着 r3 找到真正的字形来源。

═══════════════════════════════════════════════════════════════════════════
【(139) 反汇编结论】
═══════════════════════════════════════════════════════════════════════════
0x08000D9A 是 **DMA3 拷贝**：
    8000d9a: ldr  r4,[pc,#40]   → 0x040000D4  (DMA3SAD)
    8000d9c: str  r3,[r4,#0]    → DMA3SAD = r3   ← **源地址**
    8000d9e: str  r2,[r4,#4]    → DMA3DAD = r2   ← **目标（VRAM）**
    8000da0: ldr  r0,[pc,#36]   → 0x80000000
    8000da2: str  r0,[r4,#8]    → DMA3CNT（启动）
    8000da4: ldr  r0,[r4,#8]    → 读回，触发 DMA

而 (138) watchpoint 命中时：
    r3 = 0x0200453C（EWRAM）  ← 这是源地址！
    r2 = 0x06000000 / 0x06004000（VRAM 目标）

⇒ **数据先从别处到 EWRAM 0x0200453C，再 DMA 到 VRAM。**

【关键问题：0x0200453C 里的内容是什么？】
 若那是字形数据 → 说明字形是从 ROM 先解压/解到 EWRAM，再上屏。
 那就要看「谁写了 0x0200453C」。

【本脚本】
 ① GDB 在 0x08000DA4（DMA 启动后、读回时）下断点
 ② 命中后读 r3（源）和 r2（目标）
 ③ **读 r3 指向的 EWRAM 内容** → 看是不是字形
 ④ 若内容像字形，再去追「谁写进了 EWRAM」

用法：python scripts/research/firered/140_trace_dma_source.py
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

OUT = ROOT / "work" / "_probe" / "dmasrc"
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

    captured = []
    try:
        c = GdbClient("127.0.0.1", 2345, timeout=10.0)
        c.connect()

        print("① 让游戏跑到标题（3 秒）")
        try:
            c.cont(timeout=3.0)
        except GdbError:
            pass

        # 断在 DMA 启动之后（0x08000DA4），此时 r3/r2 是源/目标
        print("\n② 在 0x08000DA4（DMA3 启动后）下断点")
        c.set_sw_break(0x08000DA4, kind=2)
        # 也断在 0x08000DF2（另一条 DMA 路径）
        c.set_sw_break(0x08000DF2, kind=2)

        print("\n③ 反复 continue，收集每次 DMA 的源/目标")
        for i in range(30):
            try:
                why = c.cont(timeout=2.5)
            except GdbError:
                continue

            regs = c.cmd("g")
            raw = bytes.fromhex(regs)

            def r(n):
                return int.from_bytes(raw[n * 4:(n + 1) * 4], "little")

            pc = r(15)
            src = r(3)
            dst = r(2)
            if pc not in (0x08000DA4, 0x08000DF2):
                continue

            # 读源地址处的数据
            content = b""
            if 0x02000000 <= src < 0x03000000 or \
               0x08000000 <= src < 0x0A000000:
                try:
                    content = c.read_mem(src, 64)
                except GdbError:
                    pass

            captured.append((pc, src, dst, content))
            print(f"\n  [{i}] PC=0x{pc:08X}")
            print(f"      源 0x{src:08X}  目标 0x{dst:08X}")
            if content:
                print(f"      源数据: {content[:32].hex(' ')}")
                # nibble 分析
                nz = sum(1 for b in content for v in (b & 0xF, b >> 4) if v)
                print(f"      非零 nibble {nz}/128")

            if len(captured) >= 12:
                break

        c.close()

        # ── ④ 汇总 ─────────────────────────────────────────
        print("\n" + "=" * 78)
        print("④ 汇总")
        print("=" * 78)
        print(f"  捕获 {len(captured)} 次 DMA")
        from collections import Counter
        srcz = Counter(s >> 24 for _, s, _, _ in captured)
        print(f"  源地址区域分布：")
        for k, v in srcz.items():
            print(f"    0x{k:02X}xxxxxx: {v} 次")
        dstz = Counter(d >> 24 for _, _, d, _ in captured)
        print(f"  目标地址区域分布：")
        for k, v in dstz.items():
            print(f"    0x{k:02X}xxxxxx: {v} 次")

        # 打印所有不同源
        print(f"\n  所有源地址（去重）：")
        for s in sorted({s for _, s, _, _ in captured}):
            print(f"    0x{s:08X}")

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
