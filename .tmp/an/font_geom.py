"""font_geom.py — 量清 ROM 里 0x09400000(Middle 4bpp) 与 0x09100000(Small) 的真实几何。
只读，不改。用法: font_geom.py [rom] [--art 领,航,员]
"""
import sys

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
LIBS = {
    "MIDDLE4BPP 0x09400000": (0x09400000, 128),
    "SMALL4BPP  0x09100000": (0x09100000, 128),
    "NORMAL4BPP 0x09000000": (0x09000000, 128),
}
# charmap: 领=08BF 航=04E3 员=0FBD  地=?? 用 pack_glyph_index 反推
def pack(lead, trail):
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return (idx << 8) | trail

CHARS = {"领": 0x08BF, "航": 0x04E3, "员": 0x0FBD,
         "地": None, "图": None, "鉴": None}


def load_charmap():
    m = {}
    with open(r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\charmap.txt",
              encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if len(v) == 1:
                m[v] = int(k, 16)
    return m


def art(blk, nib_hi_first=False):
    """32B 4bpp 块 → 8x8 文本"""
    out = []
    for r in range(8):
        row = blk[r * 4:r * 4 + 4]
        s = ""
        for b in row:
            lo, hi = b & 0xF, b >> 4
            s += "#" if lo else "."
            s += "#" if hi else "."
        out.append(s)
    return out


def main():
    rom = open(ROM, "rb").read()
    cm = load_charmap()
    for c in CHARS:
        if CHARS[c] is None and c in cm:
            CHARS[c] = cm[c]
    print("charmap code:", {k: (hex(v) if v else None) for k, v in CHARS.items()})
    gids = {c: (pack(v >> 8, v & 0xFF) if v else None) for c, v in CHARS.items()}
    print("gid:", gids)

    for name, (addr, stride) in LIBS.items():
        off = addr - BASE
        print(f"\n{'='*70}\n== {name}  rom off {off:#x}  stride {stride} ==")
        for c, g in gids.items():
            if g is None:
                continue
            p = off + g * stride
            blk = rom[p:p + stride]
            nz = sum(1 for b in blk[:64] if b)
            nz2 = sum(1 for b in blk[64:stride] if b)
            print(f"\n-- {c} gid={g} ({hex(g)}) 前64B非零字节={nz} 后{stride-64}B非零={nz2}")
            up = art(blk[0:32])
            lo = art(blk[32:64])
            for a, b in zip(up, lo):
                print("   ", a, "|", b)
            if nz2:
                up2 = art(blk[64:96])
                lo2 = art(blk[96:128])
                print("    [64:128] 还有墨:")
                for a, b in zip(up2, lo2):
                    print("   ", a, "|", b)


if __name__ == "__main__":
    main()
