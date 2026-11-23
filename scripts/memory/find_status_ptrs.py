"""查状态名表指针：0x083DCAA4 区（ねむり/どく/やけど/まひ/こおり）与 0x083EAE01 区。"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def scan(rom, lo, hi, label):
    print(f"\n=== 指向 [{label}] 0x{lo:08X}..0x{hi:08X} 的 u32:")
    hits = []
    for i in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, i)[0]
        if lo <= v < hi:
            hits.append((0x08000000 + i, v))
    for a, v in hits:
        print(f"  @0x{a:08X} -> 0x{v:08X}")
    print(f"  共 {len(hits)}")
    return hits


for name in ("origin", "outputs"):
    p = (ROOT / "roms" / name /
         ("POKEMON_RUBY_AXVJ00.gba" if name == "origin"
          else "POKEMON_RUBY_AXVJ00_translated.gba"))
    if not p.is_file():
        print(f"[skip] {p}")
        continue
    rom = p.read_bytes()
    print(f"\n######## {name}: {p}")
    scan(rom, 0x083DCAA0, 0x083DCAC0, "status table A")
    scan(rom, 0x083EADF0, 0x083EAE20, "status table B")
    # dump 表本身
    for base in (0x083DCAA0, 0x083EADF0):
        b = rom[base - 0x08000000: base - 0x08000000 + 0x30]
        print(f"  dump 0x{base:08X}: " + " ".join(f"{x:02X}" for x in b))
