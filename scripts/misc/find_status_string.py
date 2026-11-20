"""找队伍状态文本：搜 ROM 里 1F 1B FF（まひ）以及指向该区的 u32 指针。"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ROM = (ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba").read_bytes()


def find(pat: bytes):
    out = []
    i = ROM.find(pat)
    while i >= 0:
        out.append(i)
        i = ROM.find(pat, i + 1)
    return out


print("1F 1B FF (まひ) 出现位置:")
for i in find(b"\x1f\x1b\xff"):
    print(f"  0x{0x08000000 + i:08X}")

print("\n指向 0x083E9A00-0x083E9C00 的 u32 字面量（ROM 内）:")
lo, hi = 0x083E9A00, 0x083E9C00
hits = []
for i in range(0, len(ROM) - 4, 4):
    v = struct.unpack_from("<I", ROM, i)[0]
    if lo <= v < hi:
        hits.append((0x08000000 + i, v))
for a, v in hits:
    print(f"  @0x{a:08X} -> 0x{v:08X}")
print(f"  共 {len(hits)}")
