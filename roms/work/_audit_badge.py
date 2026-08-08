"""Audit: where does continue-menu badge こ actually come from?"""
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
ORIGIN = (ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba").read_bytes()


def bl_target(rom: bytes, i: int) -> int | None:
    w = int.from_bytes(rom[i : i + 2], "little")
    w2 = int.from_bytes(rom[i + 2 : i + 4], "little")
    if (w & 0xF800) != 0xF000 or (w2 & 0xF800) != 0xF800:
        return None
    imm11 = w & 0x7FF
    imm11l = w2 & 0x7FF
    off = (imm11 << 12) | (imm11l << 1)
    if off & (1 << 22):
        off -= 1 << 23
    return (i + 4) + off


def find_bl_to(rom: bytes, target: int, lo: int = 0, hi: int | None = None) -> list[int]:
    if hi is None:
        hi = len(rom) - 4
    hits = []
    for i in range(lo, hi, 2):
        t = bl_target(rom, i)
        if t == target:
            hits.append(i)
    return hits


def audit_rom(path: Path) -> None:
    b = path.read_bytes()
    print("=" * 60)
    print(path)
    print("size", len(b), "sha16", __import__("hashlib").sha256(b).hexdigest()[:16])
    print("91394", b[0x91394:0x9139C].hex(" "), "vs origin", ORIGIN[0x91394:0x9139C].hex(" "))
    print("913B8", b[0x913B8:0x913BC].hex(" "), "expect 00 22 for skip-copy")
    print("913EE", b[0x913EE:0x913F2].hex(" "), "expect 00 1c 00 1c for nop-print")
    print("389DFA", b[0x389DFA:0x389DFC].hex(" "), "expect ff ff")
    print("91404 ptr", hex(int.from_bytes(b[0x91404:0x91408], "little")))
    # Is 91394 still original prologue?
    same = b[0x91394:0x913B0] == ORIGIN[0x91394:0x913B0]
    print("91394 prologue==origin?", same)

    # Search ALL 0A FF independent strings with pointers in continue band
    print("-- 0A FF near 0x389000-0x38A000 --")
    for i in range(0x389000, 0x38A000):
        if b[i : i + 2] == b"\x0a\xff":
            # find pointers to 0x08000000+i
            ptr = 0x08000000 + i
            ptrs = []
            needle = ptr.to_bytes(4, "little")
            # scan code/pools 0x90000-0x92000 and full for count
            for j in range(0x90000, 0x92000, 4):
                if b[j : j + 4] == needle:
                    ptrs.append(hex(0x08000000 + j))
            print(f"  body {hex(ptr)} ptrs_in_continue_code={ptrs}")

    # Hardcoded MOVS #0x0A in 0x90E00-0x91600
    movs = []
    for i in range(0x90E00, 0x91600, 2):
        w = int.from_bytes(b[i : i + 2], "little")
        if (w & 0xF800) == 0x2000 and (w & 0xFF) == 0x0A:
            movs.append(hex(0x08000000 + i))
    print("MOVS #0x0A in continue code:", movs)

    # Who calls 91394 / 910E4 / 90F70
    for tgt, name in [(0x91394, "badge91394"), (0x910E4, "digit910E4"), (0x90F70, "pokedex90F70")]:
        hits = find_bl_to(b, tgt, 0x90000, 0x92000)
        print(name, "callers", [hex(0x08000000 + h) for h in hits])

    # Dump digit fn: does it append 0x0A?
    print("digit910E4 bytes", b[0x910E4:0x91130].hex(" "))
    # After digit write a1 30 08 70 — any 0A nearby in that fn?
    chunk = b[0x910E4:0x91140]
    if b"\x0a" in chunk:
        print("  WARNING: 0x0A byte inside digit fn body")
    else:
        print("  no 0x0A imm in digit fn body")


for p in [
    ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba",
    ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated_new.gba",
    ROOT / "work/POKEMON_RUBY_AXVJ00_translated_tiles.gba",
]:
    if p.exists():
        audit_rom(p)
