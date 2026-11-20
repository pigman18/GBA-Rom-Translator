"""读 AXVJ 队伍菜单状态相关 ROM 数据：字符串 0x083E9AF9、表 0x0835046C / 0x083504CC。"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ROM = (ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba").read_bytes()


def off(a):
    return a - 0x08000000


def dump(a, n, label=""):
    b = ROM[off(a): off(a) + n]
    print(f"--- 0x{a:08X} ({label}) {n}B")
    for i in range(0, n, 16):
        chunk = b[i:i + 16]
        print(f"  +{i:03X}: " + " ".join(f"{x:02X}" for x in chunk))


print("字符串 0x083E9AF9 附近（状态名表）")
dump(0x083E9AC0, 0x90, "status strings")

print()
print("表 0x0835046C (24B stride)")
dump(0x0835046C, 24 * 8, "party pos table")

print()
print("表 0x083504CC")
dump(0x083504CC, 0x60, "table2")
