import struct

BIN = r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook\out\game.bin"
ROMS = [
    r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated_new.gba",
    r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba",
]

MODES = {0: "PARTITION", 1: "GRID", 2: "PTR"}


def check_bin(b):
    pat = struct.pack('<I', 0x081BB874)
    hit = None
    for i in range(len(b) - 4):
        if b[i:i + 4] == pat:
            # kOptWindow: 结构里 tpl 之后紧跟 mode(u8)。
            # 代码区的 0x081BB874 是立即数取值点，后面不会是 0/1/2 的合法 mode,
            # 这里只接受 0..2 且其后为对齐填充的那一处。
            m = b[i + 4]
            if m <= 2 and b[i + 5:i + 8] == b'\x00\x00\x00':
                hit = (i, m)
    print("  tpl/mode 命中:", hex(hit[0]) if hit else None,
          MODES.get(hit[1], hit[1]) if hit else "?")
    return hit


def find_table(b, name, pairs):
    sig = struct.pack('<%dH' % (len(pairs) * 2),
                      *[v for p in pairs for v in p])
    j = b.find(sig)
    print("  %-16s %s" % (name, hex(j) if j >= 0 else "NOT FOUND"))
    return j


def parse_inc(path):
    import re
    txt = open(path, encoding='utf-8').read()
    pat = re.compile(r"\{\s*0x([0-9A-Fa-f]{4})u,\s*0x([0-9A-Fa-f]{4})u\s*\}")
    return [(int(g, 16), int(s, 16)) for g, s in pat.findall(txt)]


base = r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook\src\text"
nrm = parse_inc(base + r"\chs_slots.inc")
sel = parse_inc(base + r"\chs_slots_sel.inc")

# 静态复核：两张表下标一一对应 + 选中槽避开引用字形与原槽
GLYPH_AVOID = [0x001, 0x021, 0x031, 0x06F, 0x077, 0x08B, 0x0FF,
               0x143, 0x145, 0x147, 0x149, 0x14B, 0x14D, 0x14F,
               0x151, 0x153, 0x159, 0x15D, 0x171, 0x18D, 0x199,
               0x1B7, 0x1BF, 0x1C3, 0x1DF, 0x1E1]
blocked = set()
for t in GLYPH_AVOID:
    blocked.add(t)
    blocked.add(t + 1)
for _g, s in nrm:
    blocked |= {s + k for k in range(4)}

assert [g for g, _ in nrm] == [g for g, _ in sel], "两表汉字顺序不一致！"
bad = [(s, sorted({s + k for k in range(4)} & blocked)) for _g, s in sel
       if {s + k for k in range(4)} & blocked]
print("静态复核: 汉字数=%d, 两表顺序一致=OK, 选中槽冲突=%s"
      % (len(nrm), bad if bad else "无"))
print("选中槽 tile 范围: %d..%d (共 %d tile)"
      % (min(s for _, s in sel), max(s for _, s in sel) + 3, len(sel) * 4))

b = open(BIN, 'rb').read()
print("game.bin size =", len(b))
check_bin(b)
find_table(b, "kOptChsSlots", nrm[:6])
find_table(b, "kOptChsSelSlots", sel[:6])

for rp in ROMS:
    try:
        r = open(rp, 'rb').read()
    except OSError:
        continue
    k = r.find(b[:64])
    same = k >= 0 and r[k:k + len(b)] == b
    print("ROM %s\n  game.bin @ %s  与ROM一致=%s"
          % (rp.split('\\')[-1], hex(k) if k >= 0 else "NOT FOUND", same))
