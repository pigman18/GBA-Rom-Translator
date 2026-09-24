"""nav_digit.py — 用屏幕上清晰的数字（引擎自带位图）当指纹，在 ROM 里找日文字库。
只读。
"""
import numpy as np

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
rom = open(ROM, "rb").read()
g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])
BASE = 0x08000000


def cell_mask(x0, y0):
    band = g[y0:y0 + 16, x0:x0 + 8]
    return (np.abs(band - WHITE).sum(2) > 60)


def tile_bytes(mask_rows):
    """8x8 bool -> 32B 4bpp（低 nibble 左像素）"""
    out = bytearray()
    for r in range(8):
        for c in range(0, 8, 2):
            lo = 1 if mask_rows[r, c] else 0
            hi = 1 if mask_rows[r, c + 1] else 0
            out.append((hi << 4) | lo)
    return bytes(out)


# row B (y24) 的右半：x184..255 应该是 "17:26"
print("== row B y24 x176..255 逐格墨量 ==")
for x0 in range(176, 256, 8):
    m = cell_mask(x0, 24)
    print(f"  x={x0:3d} 墨={int(m.sum()):3d}")

print("\n== row C y40 x176..255 逐格墨量 ==")
for x0 in range(176, 256, 8):
    m = cell_mask(x0, 40)
    print(f"  x={x0:3d} 墨={int(m.sum()):3d}")

# 取一个"看起来是数字"的格，打印 art，再拿去 ROM 全搜
for (x0, y0, tag) in ((184, 24, "B184"), (192, 24, "B192"), (200, 24, "B200"),
                      (208, 24, "B208"), (216, 24, "B216"), (224, 24, "B224")):
    m = cell_mask(x0, y0)
    print(f"\n--- ({x0},{y0}) {tag} 墨={int(m.sum())} ---")
    for r in range(16):
        print("   ", "".join("#" if v else "." for v in m[r]))

# 全 ROM 搜「上砖 32B」指纹
print("\n== ROM 指纹搜索（上砖 32B，允许 1 字节差） ==")
for (x0, y0, tag) in ((184, 24, "B184"), (192, 24, "B192"), (200, 24, "B200"),
                      (208, 24, "B208"), (216, 24, "B216"), (224, 24, "B224")):
    m = cell_mask(x0, y0)
    if m[:8].sum() == 0:
        print(f"  {tag}: 上半无墨，跳过")
        continue
    pat = tile_bytes(m[:8])
    hits = []
    start = 0
    while True:
        i = rom.find(pat, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
        if len(hits) > 30:
            break
    print(f"  {tag} 上半指纹命中 {len(hits)} 处:", [hex(h + BASE) for h in hits[:10]])
