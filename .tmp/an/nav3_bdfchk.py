import numpy as np, re, os

ROOT = r"C:\code\GBA-Rom-Translator"
CMAP = os.path.join(ROOT, "work/POKEMON_RUBY_AXVJ00/charmap.txt")
BDF = os.path.join(ROOT, "fonts/default/Middle.bdf")
A4 = np.fromfile(os.path.join(ROOT, "work/POKEMON_RUBY_AXVJ00/graphic/fonts",
                              "PokeRSFontChsMiddle_unshadow(0xE0000).bin"),
                 dtype=np.uint8)[:7168*128].reshape(7168, 128)

VALID = set(range(1, 6)) | set(range(7, 27)) | set(range(28, 31))

def slot_of(code):
    lead = code >> 8
    skip = sum(1 for L in range(0x40) if L < lead and L not in VALID)
    return (code - 0x100 * skip) & 0x1FFF

ent = []
for line in open(CMAP, encoding="utf-8", errors="replace"):
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1)
        if len(v.strip()) == 1:
            ent.append((int(k, 16), v.strip()))
inv = {slot_of(c): ch for c, ch in ent}
print("charmap 条目", len(ent), "slot 覆盖", len(inv))

# ---- 全库「梳齿行」统计 ----
def rows_of(blk):
    out = []
    for r in range(16):
        s = ""
        for b in blk[r*4:r*4+4]:
            s += "#" if (b & 0x0F) else "."
            s += "#" if (b >> 4) else "."
        out.append(s)
    return out

comb_rows_total = 0
glyphs_with_comb = 0
ink_rows_total = 0
for gi in range(7168):
    R = rows_of(A4[gi][:64])
    n = 0
    for s in R:
        ink = s.count("#")
        if 3 <= ink <= 6:
            alt = all((s[i] == "#") == (i % 2 == 0) for i in range(8)) or \
                  all((s[i] == "#") == (i % 2 == 1) for i in range(8))
            if alt:
                n += 1
        ink_rows_total += 0
    if n >= 3:
        glyphs_with_comb += 1
    comb_rows_total += n
print("全库：含 ≥3 条纯交替行的字数 = %d / 7168 (%.1f%%)"
      % (glyphs_with_comb, 100.0 * glyphs_with_comb / 7168))
print("全库：纯交替行总数 = %d" % comb_rows_total)

# ---- slot 4148 的字 + 其 BDF ----
txt = open(BDF, encoding="utf-8", errors="replace").read()
bdf = {}
for m in re.finditer(r"ENCODING\s+(\d+)\s*\n(?:.*?\n)*?BITMAP\s*\n((?:[0-9A-Fa-f]+\s*\n)+)ENDCHAR", txt):
    bdf[int(m.group(1))] = [int(l, 16) for l in m.group(2).split()]

for slot in (4148, 7028, 2883):
    ch = inv.get(slot, "?")
    print("=" * 70)
    print("slot %d -> 字符 %s (U+%04X)" % (slot, ch, ord(ch) if ch != "?" else 0))
    print("-- .bin 前 64B --")
    for s in rows_of(A4[slot][:64]):
        print("   " + s)
    key = ord(ch) if ch != "?" else None
    if key is not None and key in bdf:
        rows = bdf[key]
        print("-- BDF (%d 行, %d 位宽) --" % (len(rows), len(rows[0].__format__('016b'))))
        for k, v in enumerate(rows):
            bits = format(v, "016b")
            mark = ""
            if 2 <= k <= 12:
                mark = "   <== 墨迹区"
            print("   row%-2d %s%s" % (k, bits.replace("0", ".").replace("1", "#"), mark))
    else:
        print("-- BDF 无此 ENCODING --")
