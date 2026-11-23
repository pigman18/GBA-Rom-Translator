"""对比 origin / translated 里队伍状态相关字面量与数据。"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
O = (ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba").read_bytes()
T = (ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()


def u32(b, a):
    return struct.unpack_from("<I", b, a - 0x08000000)[0]


def dump(b, a, n):
    return b[a - 0x08000000:a - 0x08000000 + n]


POINTS = [
    (0x0806B7D8, "table 0x0835046C"),
    (0x0806B7DC, "win 0x03004170"),
    (0x0806B7E0, "status str 0x083E9AF9"),
    (0x0806B93C, "0xFFFF8000"),
    (0x0806B940, "tilemap table 0x083504CC"),
    (0x0806B944, "?"),
    (0x0806B760, "party data 0x03004290"),
]

for a, name in POINTS:
    o, t = u32(O, a), u32(T, a)
    flag = "" if o == t else "  <<< CHANGED"
    print(f"0x{a:08X} {name}: origin=0x{o:08X} trans=0x{t:08X}{flag}")

print("\n--- 状态字符串区域 0x083E9AE0..0x083E9B20")
print("origin: " + " ".join(f"{x:02X}" for x in dump(O, 0x083E9AE0, 0x40)))
print("trans : " + " ".join(f"{x:02X}" for x in dump(T, 0x083E9AE0, 0x40)))

print("\n--- 表 0x0835046C (0x60B)")
print("origin: " + " ".join(f"{x:02X}" for x in dump(O, 0x0835046C, 0x60)))
print("trans : " + " ".join(f"{x:02X}" for x in dump(T, 0x0835046C, 0x60)))

print("\n--- 表 0x083504CC (0x60B)")
print("origin: " + " ".join(f"{x:02X}" for x in dump(O, 0x083504CC, 0x60)))
print("trans : " + " ".join(f"{x:02X}" for x in dump(T, 0x083504CC, 0x60)))

print("\n--- 窗口模板 0x081BB43C (0x14B)")
print("origin: " + " ".join(f"{x:02X}" for x in dump(O, 0x081BB43C, 0x14)))
print("trans : " + " ".join(f"{x:02X}" for x in dump(T, 0x081BB43C, 0x14)))
