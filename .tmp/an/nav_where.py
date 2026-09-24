"""nav_where.py — 把屏幕上每格的「上/下砖」当 32B 模式，在字库与 ROM 里逐字节搜。
命中 ⇒ 直接给出「这块砖是从哪儿读来的」= 定位读偏移错。
ink 值按 15 编码（字库 nibble ∈ {0,15}）。只读。
"""
import numpy as np

LIB = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle_unshadow(0xE0000).bin"
ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
lib = open(LIB, "rb").read()
rom = open(ROM, "rb").read()
BASE = 0x08000000
g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])

# 先看字库里到底有哪些字节值
vals = {}
for b in lib:
    vals[b] = vals.get(b, 0) + 1
print("字库字节值分布 top10:", sorted(vals.items(), key=lambda kv: -kv[1])[:10])
print("总字节", len(lib))


def enc(mask8, ink=0xF):
    out = bytearray()
    for r in range(8):
        for c in range(0, 8, 2):
            lo = ink if mask8[r, c] else 0
            hi = ink if mask8[r, c + 1] else 0
            out.append((hi << 4) | lo)
    return bytes(out)


def search(pat, label):
    hits_lib = []
    s = 0
    while True:
        i = lib.find(pat, s)
        if i < 0:
            break
        hits_lib.append(i)
        s = i + 1
        if len(hits_lib) > 20:
            break
    hits_rom = []
    s = 0
    while True:
        i = rom.find(pat, s)
        if i < 0:
            break
        hits_rom.append(i)
        s = i + 1
        if len(hits_rom) > 20:
            break
    print(f"  {label}: 字库命中 {len(hits_lib)} {[ (h//128, h%128) for h in hits_lib[:6]]}  "
          f"ROM命中 {len(hits_rom)} {[hex(h+BASE) for h in hits_rom[:6]]}")
    return hits_lib, hits_rom


CELLS = [("A", 8, x) for x in (16, 24, 32, 40)] + \
        [("B", 24, x) for x in (16, 24, 32, 40, 72, 80, 88, 128, 136, 144)] + \
        [("C", 40, x) for x in (16, 24, 72, 80, 88, 128, 136)]
for label, y0, x0 in CELLS:
    band = g[y0:y0 + 16, x0:x0 + 8]
    m = (np.abs(band - WHITE).sum(2) > 60)
    if m.sum() == 0:
        continue
    print(f"\n{label} y{y0} x{x0} 墨={int(m.sum())}")
    search(enc(m[0:8]), f"{label}{x0} 上砖")
    search(enc(m[8:16]), f"{label}{x0} 下砖")
