"""统计某个 charblock 的 tilemap 引用范围 + VRAM 内容非空的 tile 区间。

用法: python scripts/tilemap/charblock_map.py <run_dir> <side> <frame> <charblock>
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
SIDE = sys.argv[2]
FRAME = sys.argv[3]
CB = int(sys.argv[4])

VR = 0x06000000
BASE = CB * 0x4000
TM_BASE = CB * 0x800   # 该 charblock 的 tilemap 在 VRAM 内的偏移（0x800/tilemap 假定）


def main():
    vram = (RUN / SIDE / f"{FRAME}.vram.bin").read_bytes()
    used = {}
    for y in range(32):
        row = struct.unpack_from("<32H", vram, TM_BASE + y * 64)
        for x, v in enumerate(row):
            t = v & 0x3FF
            if t == 0:
                continue
            used.setdefault(t, []).append((y, x, v >> 12))
    print(f"== {SIDE} {FRAME} charblock {CB}")
    print(f"  引用非零 tile 数={len(used)}")
    if used:
        print(f"  min=0x{min(used):03X} max=0x{max(used):03X}")
    # 分段统计
    for lo in range(0, 1024, 64):
        ts = [t for t in used if lo <= t < lo + 64]
        if ts:
            print(f"  [{lo:03X}..{lo + 63:03X}] 引用 {len(ts):3d}: " +
                  " ".join(f"{t:03X}" for t in sorted(ts)[:24]))
    # VRAM 非空 tile
    print("  VRAM 非空 tile 区间：")
    run_start = None
    for t in range(1024):
        off = BASE + t * 32
        blk = vram[off:off + 32]
        nz = any(blk)
        if nz and run_start is None:
            run_start = t
        elif not nz and run_start is not None:
            print(f"    {run_start:03X}..{t - 1:03X} ({t - run_start} tiles)")
            run_start = None
    if run_start is not None:
        print(f"    {run_start:03X}..3FF ({1024 - run_start} tiles)")


if __name__ == "__main__":
    main()
