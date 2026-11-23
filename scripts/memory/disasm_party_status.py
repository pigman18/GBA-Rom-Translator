"""反汇编 AXVJ 队伍菜单状态相关函数，并解析 PC 相对字面量池。

用法: C:\\Python314\\python.exe scripts/memory/disasm_party_status.py [start] [size]
"""
import struct
import sys
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parent.parent.parent
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
ROM = ROM_PATH.read_bytes()

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def u32(addr: int) -> int:
    return struct.unpack_from("<I", ROM, addr - 0x08000000)[0]


def u16(addr: int) -> int:
    return struct.unpack_from("<H", ROM, addr - 0x08000000)[0]


def disasm(start: int, size: int, title: str = ""):
    if title:
        print(f"### {title}")
    print(f"=== 0x{start:08X} (+0x{size:X}) ===")
    code = ROM[start - 0x08000000: start - 0x08000000 + size]
    for ins in md.disasm(code, start):
        note = ""
        if ins.mnemonic == "ldr" and "[pc" in ins.op_str:
            # ldr rX, [pc, #imm]
            imm = int(ins.op_str.split("#")[-1].rstrip("]"), 0)
            base = (ins.address + 4) & ~3
            lit_addr = base + imm
            val = u32(lit_addr)
            note = f"   ; [0x{lit_addr:08X}] = 0x{val:08X}"
            if 0x08000000 <= val < 0x0A000000:
                note += f"  -> ROM 0x{val:08X}"
        print(f"  0x{ins.address:08X}: {ins.bytes.hex():<10} {ins.mnemonic:<8} {ins.op_str}{note}")
    print()


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        disasm(int(sys.argv[1], 16), int(sys.argv[2], 16))
    else:
        disasm(0x0806B700, 0x120, "PartyMenuPutStatusTilemap / WriteTilemap")
        disasm(0x0806B810, 0x100, "PartyMenuClearLevelStatusTilemap")
        disasm(0x0806B948, 0x90, "PartyMenuDoPrintLevelOrStatus")
        disasm(0x0806B98C, 0x60, "PartyMenuPrintLevel")
        disasm(0x0806BA38, 0x60, "PartyMenuDoPrintGenderIcon")
