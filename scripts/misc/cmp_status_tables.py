"""对比状态名指针表（origin vs translated）并 dump 目标串。"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
O = (ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba").read_bytes()
T = (ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()

REGIONS = [
    (0x08015C90, 0x08015CC0, "code lit 0x08015Cxx"),
    (0x080168B0, 0x08016930, "0x080168xx"),
    (0x08017FC0, 0x08018000, "status ptr table"),
    (0x08018470, 0x080184A0, "0x080184xx"),
    (0x083A15E0, 0x083A1620, "0x083A15xx"),
]


def readstr(b, addr, limit=64):
    off = addr - 0x08000000
    if off < 0 or off >= len(b):
        return "<oob>"
    out = []
    for i in range(limit):
        c = b[off + i]
        out.append(f"{c:02X}")
        if c == 0xFF:
            break
    return " ".join(out)


for lo, hi, label in REGIONS:
    print(f"\n===== {label}  0x{lo:08X}..0x{hi:08X}")
    for a in range(lo, hi, 4):
        vo = struct.unpack_from("<I", O, a - 0x08000000)[0]
        vt = struct.unpack_from("<I", T, a - 0x08000000)[0]
        mark = "" if vo == vt else "   <<< CHANGED"
        print(f"  0x{a:08X}: origin=0x{vo:08X} trans=0x{vt:08X}{mark}")
        if vo != vt:
            print(f"        origin str: {readstr(O, vo)}")
            print(f"        trans  str: {readstr(T, vt)}")
