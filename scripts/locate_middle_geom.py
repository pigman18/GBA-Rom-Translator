"""暴力定位 Middle1Bpp 的真实打包几何与槽位映射。

思路：把某个字的 BDF 墨迹按若干候选几何打包成字节串，在 ROM 的 Middle 段里
搜索该字节串，命中的偏移 / stride 即真实槽号。候选几何对不上就换下一个。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BDF = ROOT / "fonts" / "default" / "Middle.bdf"
CMAP = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "charmap.txt"

ROM_BASE = 0x08000000
ADDR = 0x09700000
SIZE = 0x16C00
SLOTS = 7168
CH = "文"


def load_bdf_ink(cp, cols, rows, y0):
    txt = BDF.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"ENCODING\s+%d\s*\n(?:.*?\n)*?BITMAP\s*\n((?:[0-9A-Fa-f]+\s*\n)+)ENDCHAR"
                  % cp, txt)
    if not m:
        return None
    raw = [int(l, 16) for l in m.group(1).split()]
    g = []
    for r in range(rows):
        y = y0 + r
        row = raw[y] if 0 <= y < len(raw) else 0
        g.append([(row >> (15 - c)) & 1 for c in range(cols)])
    return g


def pack(g, cols, rows, x0):
    stride = (cols * rows + 7) // 8
    out = bytearray(stride)
    bit = 0
    for r in range(rows):
        for c in range(cols):
            if g[r][c + x0] if (c + x0) < len(g[r]) else 0:
                out[bit >> 3] |= 0x80 >> (bit & 7)
            bit += 1
    return bytes(out)


def main():
    cm = {}
    for line in CMAP.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            if len(v.strip()) == 1:
                cm.setdefault(v.strip(), int(k, 16))
    slot_key = cm.get(CH)
    print("charmap: %s → 0x%04X（&0x1FFF = 0x%04X）" % (CH, slot_key, slot_key & 0x1FFF))

    rom = ROM.read_bytes()
    off = ADDR - ROM_BASE
    seg = rom[off:off + SIZE]
    nz = sum(1 for b in seg if b)
    print("Middle 段: %d B, 非零 %d (%.1f%%), 按 13B 共 %d 槽\n"
          % (len(seg), nz, 100.0 * nz / len(seg), len(seg) // 13))

    for cols, rows, y0 in ((9, 11, 2), (8, 11, 2), (9, 11, 3), (9, 11, 1), (11, 11, 2)):
        g = load_bdf_ink(ord(CH), cols, rows, y0)
        if g is None:
            continue
        for x0 in range(0, max(1, cols - 6)):
            pat = pack(g, cols, rows, x0)
            stride = len(pat)
            hits = []
            start = 0
            while True:
                i = seg.find(pat, start)
                if i < 0:
                    break
                hits.append(i)
                start = i + 1
                if len(hits) > 4:
                    break
            if hits:
                print("命中！几何 cols=%d rows=%d y0=%d x0=%d stride=%dB"
                      % (cols, rows, y0, x0, stride))
                for h in hits[:4]:
                    print("    偏移 0x%05X  槽(÷%d)=0x%04X  期望槽=0x%04X  %s"
                          % (h, stride, h // stride, slot_key & 0x1FFF,
                             "★" if h // stride == (slot_key & 0x1FFF) else ""))
                return 0
    print("所有候选几何都没搜到 —— 说明 pack 前对字形做过重采样/归一化，需读 build_chinese_font.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
