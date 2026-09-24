"""探针：ROM 中 Middle 字库的真实落点。

font.config.json 里有两个 Middle：
  extra_bins  Middle1Bpp  addr=158334976 (0x09700000)  13 B/字   ← 1bpp 紧凑库
  font_slots  Middle      addr=155189248 (0x09400000)  128 B/字  ← 4bpp 独占槽
本脚本量两个地址的字节密度 + 用 13B 步进解一个字，判断哪个真装着 1bpp 字库。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
CANDS = [(0x09700000, "Middle1Bpp(13B/字)"), (0x09400000, "Middle slot(128B/字)"),
         (0x09600000, "Small1Bpp(11B/字)"), (0x09500000, "Big1Bpp(16B/字)")]


def unpack13(buf, cols, rows):
    """按 1bpp 连续位流解 cols×rows"""
    out = []
    for r in range(rows):
        row = []
        for c in range(cols):
            bit = r * cols + c
            row.append('#' if (buf[bit >> 3] >> (7 - (bit & 7))) & 1 else '.')
        out.append(''.join(row))
    return out


def main():
    rom = ROM.read_bytes()
    print("ROM:", ROM.name, " sha1 见外部")
    for addr, name in CANDS:
        off = addr - BASE
        win = rom[off:off + 13 * 7168]
        nz = sum(1 for b in win if b)
        head = win[:32].hex(' ')
        print("\n=== 0x%08X  %s ===" % (addr, name))
        print("  窗口 %d B，非零字节 %d (%.1f%%)" % (len(win), nz, 100.0 * nz / len(win)))
        print("  前 32B:", head)
        # 以 7168 槽中第 2000 槽为例，用 13B 步进解
        for stride, cols, rows, tag in ((13, 9, 11, "13B/9x11"), (128, 9, 11, "128B/9x11")):
            blk = rom[off + 2000 * stride: off + 2000 * stride + stride]
            if not any(blk):
                continue
            print("  槽2000 @stride%d %s:" % (stride, tag))
            for r in unpack13(blk, cols, rows):
                print("     ", r)


if __name__ == "__main__":
    raise SystemExit(main())
