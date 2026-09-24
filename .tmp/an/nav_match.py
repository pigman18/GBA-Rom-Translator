"""nav_match.py — 判定屏幕上每格到底是什么：原字 / 上下换砖 / 混叠。只读。"""
import numpy as np

LIB = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle_unshadow(0xE0000).bin"
raw = open(LIB, "rb").read()
NG, ST = 7168, 128


def to_bitmap(blk64):
    """64B 4bpp (TL 32B + BL 32B) -> 16x8 bool"""
    m = np.zeros((16, 8), bool)
    for half in range(2):
        for r in range(8):
            row = blk64[half * 32 + r * 4: half * 32 + r * 4 + 4]
            for ci, b in enumerate(row):
                m[half * 8 + r, ci * 2] = (b & 0xF) != 0
                m[half * 8 + r, ci * 2 + 1] = (b >> 4) != 0
    return m


GLY = np.zeros((NG, 16, 8), bool)
for g in range(NG):
    GLY[g] = to_bitmap(raw[g * ST: g * ST + 64])
print("glyph bitmaps ready:", GLY.shape)

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])

LINES = {"A 标题": 8, "B 行1": 24, "C 行2": 40}
XS = {"A 标题": [16, 24, 32, 40], "B 行1": [16, 24, 32, 40], "C 行2": [16, 24, 32, 40]}

for label, y0 in LINES.items():
    band = g[y0:y0 + 16, 0:240]
    m = (np.abs(band - WHITE).sum(2) > 60)
    for x0 in XS[label]:
        cell = m[:, x0:x0 + 8]
        n = int(cell.sum())
        if n == 0:
            continue
        # (a) 原字
        d_a = (GLY[:, :, :] != cell).reshape(NG, -1).sum(1)
        ia = int(d_a.argmin())
        # (b) 同字上下换砖
        swap = np.concatenate([cell[8:16], cell[0:8]], axis=0)
        d_b = (GLY != swap).reshape(NG, -1).sum(1)
        ib = int(d_b.argmin())
        print(f"{label} x={x0:3d} 墨={n:3d} | 原字: gid={ia:4d} d={d_a[ia]:3d} | "
              f"换砖: gid={ib:4d} d={d_b[ib]:3d}")
        if d_b[ib] <= 6:
            print("      ↳ 换砖命中，字形：")
            for r in range(16):
                print("       ", "".join("#" if v else "." for v in GLY[ib][r]),
                      "  <-- 屏幕" if False else "")
            print("      屏幕实际：")
            for r in range(16):
                print("       ", "".join("#" if v else "." for v in cell[r]))
