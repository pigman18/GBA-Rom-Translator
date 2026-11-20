"""dump Small / Normal 中文字库里某几个字的 16x16 slot，看墨迹的 x/y 范围。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "graphic" / "fonts"

CHARMAP = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "charmap.txt"
LEAD_ADJUST = lambda h: h - 1 - (1 if h >= 6 else 0) - (1 if h >= 0x1B else 0)


def load_charmap():
    m = {}
    for line in CHARMAP.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        code, ch = line.split("=", 1)
        code = code.strip()
        ch = ch.strip()
        if len(code) != 4:
            continue
        try:
            hi, lo = int(code[:2], 16), int(code[2:], 16)
        except ValueError:
            continue
        m[ch] = (hi, lo)
    return m


def glyph_index(hi, lo):
    return LEAD_ADJUST(hi) * 256 + lo


def dump_slot(buf, idx, label):
    off = idx * 128
    slot = buf[off:off + 128]
    print(f"  {label} slot {idx} (0x{off:06X})")
    # 4bpp, TL(0..31) BL(32..63) TR(64..95) BR(96..127)
    rows = []
    for y in range(16):
        line = ""
        for x in range(16):
            tile = (x >> 3) * 2 + (y >> 3)
            o = tile * 32 + (y & 7) * 4 + ((x & 7) >> 1)
            b = slot[o]
            v = (b >> 4) if (x & 1) else (b & 0xF)
            line += "." if v == 0 else ("#" if v == 15 else ("s" if v == 14 else f"{v:X}"))
        rows.append(line)
    for y, line in enumerate(rows):
        print(f"    y={y:2d} {line}")
    xs, ys = [], []
    for y in range(16):
        for x in range(16):
            tile = (x >> 3) * 2 + (y >> 3)
            o = tile * 32 + (y & 7) * 4 + ((x & 7) >> 1)
            b = slot[o]
            v = (b >> 4) if (x & 1) else (b & 0xF)
            if v:
                xs.append(x)
                ys.append(y)
    if xs:
        print(f"    ink bbox x=[{min(xs)},{max(xs)}] y=[{min(ys)},{max(ys)}]")
    else:
        print("    EMPTY")


def main():
    cm = load_charmap()
    print(f"charmap 条目 {len(cm)}")
    for label, name in (("Small", "PokeRSFontChsSmall(0xE0000).bin"),
                        ("Normal", "PokeRSFontChsNormal(0xE0000).bin")):
        p = FONTS / name
        if not p.is_file():
            print(f"[skip] {p}")
            continue
        buf = p.read_bytes()
        print(f"\n=== {label}  {p.name}  {len(buf)}B")
        for ch in ("麻", "痹", "宝", "梦"):
            if ch not in cm:
                print(f"  {ch} 不在 charmap")
                continue
            hi, lo = cm[ch]
            dump_slot(buf, glyph_index(hi, lo), f"{ch} hi={hi:02X} lo={lo:02X}")


if __name__ == "__main__":
    main()
