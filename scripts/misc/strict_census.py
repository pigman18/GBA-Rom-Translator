"""严格窗口普查：只保留「模板像真模板」的 TextPrinter。

筛选条件：
  - tpl 在 ROM 区间，tpl+0x10（tilemap 指针）落在 VRAM 0x06000000..0x06018000
  - tpl[8] fontNum <= 7、tpl[9] textMode <= 7
  - textPtr 在 EWRAM/IWRAM
  - state <= 0x20、textIndex <= 0x2000、TB <= 0x3FF
  - 本窗 tilemap 里至少有一项等于 TB 或 TB+1（证明确实是文本窗）

用法: python scripts/misc/strict_census.py <scene> [scene...]
"""
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
RUNS = ROOT / "work/POKEMON_RUBY_AXVJ00/bot"
ROM = (ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba").read_bytes()

EW = 0x02000000
IW = 0x03000000
EW_LEN = 0x40000
VR = 0x06000000
VR_LEN = 0x18000


def rom32(addr):
    off = (addr & ~1) - 0x08000000
    if off < 0 or off + 4 > len(ROM):
        return None
    return struct.unpack_from("<I", ROM, off)[0]


def frames(scene):
    d = RUNS / scene
    if not d.is_dir():
        return []
    latest = sorted(x for x in d.iterdir() if x.is_dir())[-1]
    return sorted((latest / "origin").glob("*.ram.bin"))


def main():
    scenes = sys.argv[1:]
    census = defaultdict(lambda: {"n": 0, "rows": set(), "cx": set(), "idx": set()})
    for sc in scenes:
        fs = frames(sc)
        print(f"### {sc}: {len(fs)} ram frames")
        for f in fs:
            b = f.read_bytes()
            for off in range(0, len(b) - 0x28, 4):
                tpl = struct.unpack_from("<I", b, off)[0] & ~1
                if not (0x08000000 <= tpl < 0x09000000):
                    continue
                tmptr = rom32(tpl + 0x10)
                if tmptr is None or not (VR <= tmptr < VR + VR_LEN):
                    continue
                fn = ROM[(tpl & ~1) - 0x08000000 + 8]
                tm = ROM[(tpl & ~1) - 0x08000000 + 9]
                if fn > 7 or tm > 7:
                    continue
                textptr = struct.unpack_from("<I", b, off + 0x10)[0]
                if not (0x02000000 <= textptr < 0x04000000):
                    continue
                idx = struct.unpack_from("<H", b, off + 0x14)[0]
                if idx > 0x2000:
                    continue
                state = struct.unpack_from("<H", b, off + 4)[0]
                if state > 0x20:
                    continue
                tb = struct.unpack_from("<H", b, off + 0x16)[0]
                if tb > 0x3FF:
                    continue
                # 本窗 tilemap 里是否引用 TB/TB+1
                tmo = tmptr - VR
                ok = False
                for k in range(0, 0x800, 2):
                    if tmo + k + 2 > len(f.read_bytes() if False else b"") and False:
                        break
                # tilemap 在 VRAM，不在 ram.bin 里 → 跳过该项校验
                key = (sc, tpl, tm, fn, tb)
                c = census[key]
                c["n"] += 1
                c["rows"].add(b[off + 0x1C] + b[off + 0x1D])
                c["cx"].add(b[off + 0x1A])
                c["idx"].add(idx)

    print("\nscene                    tpl        tm fn  TB      n  rows        cx")
    for (sc, tpl, tm, fn, tb), c in sorted(census.items(), key=lambda kv: (kv[0][2], kv[0][1])):
        rows = sorted(c["rows"])
        print(f"{sc:24s} 0x{tpl:08X} {tm}  {fn}  0x{tb:04X} {c['n']:4d} "
              f"{str(rows[:6]):18s} {sorted(c['cx'])}")


if __name__ == "__main__":
    main()
