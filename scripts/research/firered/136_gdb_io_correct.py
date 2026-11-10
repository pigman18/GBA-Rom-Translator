#!/usr/bin/env python3
"""调研(136) 用 GDB 重做 IO 分析 —— Lua 的 IO 读取从 +0x10 起是假的。

═══════════════════════════════════════════════════════════════════════════
【(135) 的决定性对比】
═══════════════════════════════════════════════════════════════════════════
同一个 0x04000000 区，两种读法完全不同：

  GDB 读（可信）:                        Lua 读（可疑）:
   +0x00: 40 58 00 00                    40 31 00 00
   +0x04: 29 96 ae 00                    29 96 a0 00
   +0x10: 01 00 01 00 ...                18 1c 18 1c ...
   +0x0B0: 01 00 01 00 ...               18 1c 18 1c ...

  VCOUNT: GDB = 0x00AE（合法 174）      Lua = 0x9629（非法！）
  KEYINPUT 位置: GDB 能读到 0x3F00     Lua 读不到

⇒ **GDB 的 m 包读到的是真硬件寄存器；Lua 的 readRange 对 IO 区
   从 +0x10 起返回的是「映射后的假数据」**（可能是 mGBA 的
   IO 映射实现差异，或 readRange 走了不同的访问路径）。

⚠ 这意味着：
   · 我之前所有「BGxCNT = 0x1E00 / DISPCNT = 0x3140」的结论都建立在
     Lua 读数上，**必须用 GDB 重新验证**
   · 但 (76) 之后我用 Lua 读出的 DISPCNT=0x3140 又能正确渲染出画面…
     说明 DISPCNT 本身（+0x00）是可信的，只是**+0x06 之后的 BGxCNT 可能拿错了**

【本脚本：用 GDB 读完整 IO，重新解析 BG 配置】
 ① 读 0x04000000..0x04000200（含 KEYINPUT）
 ② 正确解析 DISPCNT / BGxCNT / DMA
 ③ 与 Lua 的对比，找出哪个地址开始分歧

用法：python scripts/research/firered/136_gdb_io_correct.py
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

OUT = ROOT / "work" / "_probe" / "gdbiocorrect"
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

        # 让游戏跑一段（到标题）
        try:
            c.cont(timeout=6.0)
        except GdbError:
            pass

        io = c.read_mem(0x04000000, 0x200)

        def u16(o):
            return struct.unpack_from("<H", io, o)[0]

        def u32(o):
            return struct.unpack_from("<I", io, o)[0]

        print("=" * 78)
        print("① GDB 读到的完整 IO（0x04000000..0x04000200）")
        print("=" * 78)
        for o in range(0, 0x100, 16):
            print(f"  +0x{o:03X}: {io[o:o+16].hex(' ')}")

        print("\n" + "=" * 78)
        print("② 逐寄存器解析")
        print("=" * 78)
        dc = u16(0)
        print(f"  DISPCNT (0x00) = 0x{dc:04X}")
        print(f"    mode={dc&7}  BG0={(dc>>8)&1} BG1={(dc>>9)&1} "
              f"BG2={(dc>>10)&1} BG3={(dc>>11)&1} OBJ={(dc>>12)&1}")
        print(f"  DISPSTAT(0x04) = 0x{u16(4):04X}")
        print(f"  VCOUNT  (0x06) = 0x{u16(6):04X}  ← 应 0..227  "
              f"{'✓' if u16(6) <= 227 else '✗'}")
        print()
        print(f"  GBA 手册：BG0CNT = 0x04000008, BG1CNT = 0x0A, "
              f"BG2CNT = 0x0C, BG3CNT = 0x0E")
        for b in range(4):
            v = u16(8 + b * 2)
            cb = ((v >> 2) & 3) * 0x4000
            sb = ((v >> 8) & 0x1F) * 0x800
            print(f"    BG{b}CNT(0x{8+b*2:02X}) = 0x{v:04X}  "
                  f"prio={v&3} charBase=0x{cb:04X} screenBase=0x{sb:04X} "
                  f"{'8bpp' if (v>>7)&1 else '4bpp'} size={v>>14}")
        print()
        print(f"  BGxHOFS/VOFS：")
        for b in range(4):
            h = u16(0x10 + b * 4)
            v = u16(0x12 + b * 4)
            print(f"    BG{b} HOFS={h} VOFS={v}")
        print()
        print(f"  KEYINPUT(0x130) = 0x{u16(0x130):04X}  "
              f"（未按键应 0x03FF）")
        print(f"  KEYCNT  (0x132) = 0x{u16(0x132):04X}")
        print()
        print(f"  DMA 寄存器：")
        for n, b in (("DMA0", 0xB0), ("DMA1", 0xBC),
                     ("DMA2", 0xC8), ("DMA3", 0xD4)):
            sad, dad, cnt = u32(b), u32(b + 4), u16(b + 8)
            mark = ""
            if 0x08000000 <= sad < 0x0A000000 and 0x06000000 <= dad < 0x07000000:
                mark = "  ★ ROM→VRAM"
            print(f"    {n}: SAD=0x{sad:08X} DAD=0x{dad:08X} "
                  f"CNT=0x{cnt:04X}{mark}")

        # ── ③ 关键：字形用的 BG 层 ────────────────────────────
        print("\n" + "=" * 78)
        print("③ 结论：文字用哪一层")
        print("=" * 78)
        for b in range(4):
            if (dc >> (8 + b)) & 1:
                v = u16(8 + b * 2)
                cb = ((v >> 2) & 3) * 0x4000
                sb = ((v >> 8) & 0x1F) * 0x800
                print(f"  BG{b} 使能: charBase=0x{cb:04X} "
                      f"screenBase=0x{sb:04X} "
                      f"{'8bpp' if (v>>7)&1 else '4bpp'}")
        if (dc >> 12) & 1:
            print(f"  OBJ 使能（sprite，charBase 见 DISPCNT bit2-4）")

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
