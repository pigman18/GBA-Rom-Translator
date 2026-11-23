"""扫多个场景 run 的所有 TextPrinter，统计 (tpl, textMode, fontNum, TB) 分布。

用法: python scripts/window/tb_census.py <scene1> <scene2> ...
每个 scene 取 work/POKEMON_RUBY_AXVJ00/bot/<scene>/ 下最新 run，扫全部有 ram.bin 的帧
（origin 侧）。
"""
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
RUNS = ROOT / "work/POKEMON_RUBY_AXVJ00/bot"
EW = 0x02000000
IW = 0x03000000
EW_LEN = 0x40000


def frames(scene):
    d = RUNS / scene
    if not d.is_dir():
        return []
    latest = sorted(x for x in d.iterdir() if x.is_dir())[-1]
    return sorted((latest / "origin").glob("*.ram.bin"))


def main():
    scenes = sys.argv[1:]
    census = defaultdict(lambda: {"frames": 0, "rows": []})
    for sc in scenes:
        fs = frames(sc)
        print(f"### {sc}: {len(fs)} ram frames")
        for f in fs:
            b = f.read_bytes()
            for off in range(0, len(b) - 0x28, 4):
                tpl = struct.unpack_from("<I", b, off)[0] & ~1
                if not (0x08000000 <= tpl < 0x09000000):
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
                tm = b[off + 0x0A]
                fn = b[off + 0x0B]
                key = (sc, tpl, tm, fn, tb)
                c = census[key]
                c["frames"] += 1
                row = b[off + 0x1C] + b[off + 0x1D]
                c["rows"].append(row)
    print("\nscene/tpl/tm/fn/TB  frames  row-range  grid_t0(col=0)")
    for (sc, tpl, tm, fn, tb), c in sorted(census.items()):
        rows = c["rows"]
        t0s = sorted({tb + 2 + (r & 7) * 62 for r in rows})
        print(f"{sc:24s} 0x{tpl:08X} tm={tm} fn={fn} TB=0x{tb:04X} n={c['frames']:4d} "
              f"row={min(rows)}..{max(rows)} t0={['0x%03X' % t for t in t0s]}")


if __name__ == "__main__":
    main()
