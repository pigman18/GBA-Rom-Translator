#!/usr/bin/env python3
"""调研(135) 用 GDB 读 IO 区，与 Lua dump 对比 —— 找出哪个可信。

═══════════════════════════════════════════════════════════════════════════
【(134) 的异常】
═══════════════════════════════════════════════════════════════════════════
Lua dump 的 0x04000000..0x04000100：
    +0x000: 40 31 00 00 29 96 a0 00 00 1e 00 00 00 00 0f 1c  ← 前 16 字节合理
    +0x010: 18 1c 18 1c 18 1c ...                           ← ★ 全是重复值！
    +0x0B0: 18 1c 18 1c 18 1c 18 1c 00 00 60 00 18 1c ...

从 +0x10 起全是 `0x1C18` 重复，这**不可能是寄存器**。
（0x04000010 是 BG0HOFS，最大 511；0x040000B0 是 DMA0SAD，不可能 0x1C181C18）

⇒ mGBA 的 readRange 对 IO 区从某处开始返回假数据。

【验证：GDB 的 m 包直接读内存】
 GDB stub 的 `m addr,len` 走的是模拟器的**内存接口**，与 Lua 的 readRange
 可能是不同路径。对比两者就能知道谁对。

【本脚本】
 ① mGBA --gdb 启动，跑到标题（不按键）
 ② GDB 读 0x04000000..0x100
 ③ 与已知的 Lua dump 对比
 ④ 若 GDB 读到的是真寄存器（DMA 有合理值），说明 Lua 的 IO 读取不可信，
    之前所有「IO 分析」都要重做

用法：python scripts/research/firered/135_gdb_vs_lua_io.py
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

OUT = ROOT / "work" / "_probe" / "iocmp"
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
    print("① 启动 mGBA --gdb")
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(4)

    try:
        c = GdbClient("127.0.0.1", 2345, timeout=10.0)
        c.connect()

        print("\n② 先让游戏跑一会儿（cont 5 秒，超时算正常）")
        try:
            c.cont(timeout=5.0)
        except GdbError:
            pass    # 超时正常

        print("\n③ GDB 读 IO 区 0x04000000..0x04000100")
        try:
            io = c.read_mem(0x04000000, 0x100)
        except GdbError as e:
            print(f"  读失败：{e}")
            c.close()
            return 1

        print(f"  读到 {len(io)} 字节")
        for o in range(0, 0x100, 16):
            print(f"    +0x{o:03X}: {io[o:o+16].hex(' ')}")

        # 解析关键寄存器
        print("\n④ 解析")
        import struct

        def u16(o):
            return struct.unpack_from("<H", io, o)[0]

        def u32(o):
            return struct.unpack_from("<I", io, o)[0]

        dc = u16(0)
        print(f"  DISPCNT = 0x{dc:04X}  "
              f"BG0-3={(dc>>8)&0xF:04b} OBJ={(dc>>12)&1} mode={dc&7}")
        print(f"  VCOUNT  = 0x{u16(6):04X}（应 0..227）")
        print(f"  BG0CNT  = 0x{u16(8):04X}")
        print(f"  BG1CNT  = 0x{u16(0xA):04X}")
        print(f"  KEYINPUT= 0x{u16(0x130):04X}（未按键应 0x03FF）")
        print(f"\n  DMA:")
        for n, b in (("DMA0", 0xB0), ("DMA1", 0xBC),
                     ("DMA2", 0xC8), ("DMA3", 0xD4)):
            print(f"    {n}SAD=0x{u32(b):08X} DAD=0x{u32(b+4):08X} "
                  f"CNT=0x{u16(b+8):04X}")

        # ── ⑤ 判断 IO 是否可信 ────────────────────────────────
        print("\n" + "=" * 78)
        print("⑤ 判读")
        print("=" * 78)
        vc = u16(6)
        key = u16(0x130)
        # 找 0x1C18 重复
        rep = sum(1 for o in range(0x10, 0x100, 2) if u16(o) == 0x1C18)
        print(f"  0x1C18 出现次数（0x10..0x100）：{rep} / {(0x100-0x10)//2}")
        if rep > 40:
            print(f"  ⇒ 仍是假数据（重复填充），IO 区读取有问题")
        else:
            print(f"  ⇒ 与 Lua dump 不同！GDB 读到了不同内容")

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
