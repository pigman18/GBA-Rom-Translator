"""对比 bot 帧的 VRAM：找出 origin vs translated 差异 tile，并 dump 状态区 tilemap。

用法:
  python scripts/tilemap/vram_diff.py <run_dir> <frame>
"""
import struct
import sys
from pathlib import Path

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]

TILE_BYTES = 32


def load(side, name):
    return (RUN / side / f"{FRAME}.{name}.bin").read_bytes()


def tiles(vram):
    return [vram[i:i + TILE_BYTES] for i in range(0, len(vram) - 31, TILE_BYTES)]


def main():
    ov = load("origin", "vram")
    tv = load("translated", "vram")
    oio = load("origin", "io")
    tio = load("translated", "io")

    dispcnt = struct.unpack_from("<H", oio, 0)[0]
    print(f"DISPCNT origin=0x{dispcnt:04X} translated=0x{struct.unpack_from('<H', tio, 0)[0]:04X}")
    for i in range(4):
        c = struct.unpack_from("<H", oio, 8 + i * 2)[0]
        en = "on" if dispcnt & (0x100 << i) else "off"
        print(f"  BG{i}CNT=0x{c:04X} prio={c & 3} charBase=0x{(c >> 2) & 3} "
              f"mos={((c >> 14) & 1)} cm={((c >> 7) & 1)} screenBase=0x{(c >> 8) & 0x1F} {en}")

    ot, tt = tiles(ov), tiles(tv)
    diff = [i for i in range(min(len(ot), len(tt))) if ot[i] != tt[i]]
    print(f"\n差异 tile 数: {len(diff)} / {len(ot)}")
    print("前 60 个差异 tile 号:", [f"0x{i:03X}" for i in diff[:60]])

    # 按 0x100 分块统计
    buckets = {}
    for i in diff:
        buckets.setdefault(i >> 8, []).append(i)
    print("\n按 256 tile 分块:")
    for b in sorted(buckets):
        idxs = buckets[b]
        print(f"  0x{b:02X}xx : {len(idxs)} 个  {[f'0x{i:03X}' for i in idxs[:12]]}")

    def show_tile(i):
        print(f"\n--- tile 0x{i:03X} (vram +0x{i*32:05X})")
        for tag, src in (("origin", ot[i]), ("trans", tt[i])):
            print(f"  {tag}:")
            for r in range(8):
                row = src[r * 4:(r + 1) * 4]
                print("    " + " ".join(f"{x:02X}" for x in row)
                      + "   " + " ".join(f"{x & 0xF:X}{x >> 4:X}" for x in row))

    for i in diff[:6]:
        show_tile(i)


if __name__ == "__main__":
    main()
