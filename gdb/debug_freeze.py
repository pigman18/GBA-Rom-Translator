#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_freeze.py — 游戏卡死时抓现场（只读，不改任何内存/寄存器）。

连接 mGBA GDB stub（127.0.0.1:2345），要求游戏已处于冻结状态：
  1. PC / LR / sp + r0-r3（PC 直接指认死循环指令）
  2. PC 处 32B 指令字节
  3. TextPrinter 结构（win=0x0202E658）关键字段
  4. CHS pitch ctrl + 8 个 slot 状态

用法：
  mGBA 卡死画面 → Tools → Start GDB stub（2345）→ Pause →
  python gdb/debug_freeze.py [win_addr]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from util.debug_patcher import GdbClient, GdbError  # noqa: E402

HOST, PORT = "127.0.0.1", 2345
DEFAULT_WIN = 0x0202E658
PITCH_CTRL = 0x0203FF80
PITCH_SLOTS = 0x0203FF90


def u16(b, o):
    return b[o] | (b[o + 1] << 8)


def u32(b, o):
    return b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)


def region_of(addr):
    if 0x08000000 <= addr < 0x0A000000:
        return "ROM"
    if 0x02000000 <= addr < 0x02040000:
        return "EWRAM"
    if 0x03000000 <= addr < 0x03008000:
        return "IWRAM"
    if 0x05000000 <= addr < 0x06000000:
        return "PAL/VRAM/OBJ"
    if 0x04000000 <= addr < 0x04000400:
        return "IO"
    if addr < 0x04000000:
        return "BIOS/低"
    return "其它"


def main():
    win_addr = int(sys.argv[1], 16) if len(sys.argv) > 1 else DEFAULT_WIN
    g = GdbClient(HOST, PORT, timeout=5.0)
    g.connect()
    try:
        regs = g.read_regs()
        pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
        lr = (regs.get("r14", 0) & ~1) & 0xFFFFFFFF
        print(f"PC=0x{pc:08X} ({region_of(pc)})  LR=0x{lr:08X} ({region_of(lr)})")
        print(f"sp=0x{regs.get('r13', 0):08X}")
        for i in range(4):
            print(f"r{i}=0x{regs.get(f'r{i}', 0):08X}", end="  ")
        print()

        code = bytes(g.read_mem(pc & ~1, 32))
        print(f"code@PC: {code.hex(' ')}")

        wb = bytes(g.read_mem(win_addr, 0x22))
        tptr = u32(wb, 0x10)
        print(f"\nwin=0x{win_addr:08X}: {wb.hex(' ')}")
        print(
            f"  state={wb[4]} textPtr=0x{tptr:08X}({region_of(tptr)})"
            f" textIndex={u16(wb, 0x14)}"
        )
        print(
            f"  TILE_BASE=0x{u16(wb, 0x16):04X} TILE_OFF=0x{u16(wb, 0x18):04X}"
            f" curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
            f" textMode={wb[0x0A]} fontNum={wb[0x0B]}"
        )

        ctrl = bytes(g.read_mem(PITCH_CTRL, 16))
        print(f"\npitch_ctrl @0x{PITCH_CTRL:08X}: {ctrl.hex(' ')}")
        slots = bytes(g.read_mem(PITCH_SLOTS, 64))
        for i in range(8):
            s = slots[i * 8 : (i + 1) * 8]
            print(
                f"  slot{i}: char_base={s[0]} write_op={s[1]} base_tx={s[2]}"
                f" last_adv={s[3]} pitch_key=0x{u16(s, 4):04X} chs_px={u16(s, 6)}"
            )
    except GdbError as e:
        print(f"GDB 错误: {e}")
        return 1
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
