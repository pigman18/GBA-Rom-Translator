"""精确反汇编 0x0806B6BC..0x0806B9AC 一带（队伍菜单状态绘制链）。"""
import struct
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parent.parent.parent
ROM = (ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba").read_bytes()
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def u32(a):
    return struct.unpack_from("<I", ROM, a - 0x08000000)[0]


def dis(start, size, title):
    print(f"\n### {title}  0x{start:08X} +0x{size:X}")
    code = ROM[start - 0x08000000:start - 0x08000000 + size]
    for ins in md.disasm(code, start):
        note = ""
        if "[pc" in ins.op_str:
            imm = int(ins.op_str.split("#")[-1].rstrip("]"), 0)
            lit = ((ins.address + 4) & ~3) + imm
            v = u32(lit)
            note = f"   ; [0x{lit:08X}]=0x{v:08X}"
            if 0x08000000 <= v < 0x09000000:
                tail = ROM[v - 0x08000000:v - 0x08000000 + 16]
                note += "  ROM: " + " ".join(f"{b:02X}" for b in tail)
        print(f"  0x{ins.address:08X}: {ins.bytes.hex():<10} {ins.mnemonic:<7} {ins.op_str}{note}")


dis(0x0806B6BC, 0x30, "0x0806B6BC (called by DoPrintMonNickname)")
dis(0x0806B7E4, 0x2C, "PartyMenuPutStatusTilemap wrapper")
dis(0x0806B88C, 0xBC, "0x0806B88C (draws level/status)")
