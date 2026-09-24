"""nav_split.py — 判定每格的「上半 / 下半」各是哪个字模的哪一半。
假设：格子 = (某字的 BL, 某字的 TL) —— 用来区分「同字上下换砖」vs「整条 map 偏一格」。只读。
"""
import numpy as np

LIB = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle_unshadow(0xE0000).bin"
raw = open(LIB, "rb").read()
NG, ST = 7168, 128


def to_bitmap(blk64):
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
    GLY[g] = to_bitmap(raw[g * ST:g * ST + 64])
TL = GLY[:, 0:8, :]
BL = GLY[:, 8:16, :]

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])

# line A: y8..24   line B: y24..40   line C: y40..56；每行格起点 x=16,24,32,40（标题 4 格）
for label, y0 in (("A 标题", 8), ("B 行1", 24), ("C 行2", 40)):
    band = g[y0:y0 + 16, 0:240]
    m = (np.abs(band - WHITE).sum(2) > 60)
    print(f"\n===== {label} (y {y0}..{y0+15}) =====")
    for x0 in (16, 24, 32, 40, 48, 72, 80, 128, 136, 184, 192):
        cell = m[:, x0:x0 + 8]
        if cell.sum() == 0:
            continue
        up, lo = cell[0:8], cell[8:16]
        dA = (BL != up).reshape(NG, -1).sum(1)
        dB = (TL != lo).reshape(NG, -1).sum(1)
        iA, iB = int(dA.argmin()), int(dB.argmin())
        # 同字（BL/TL 同 gid）
        same = dA + dB
        iS = int(same.argmin())
        print(f" x={x0:3d} 墨={int(cell.sum()):3d} | 上半≈BL(gid={iA:4d}) d={dA[iA]:2d} | "
              f"下半≈TL(gid={iB:4d}) d={dB[iB]:2d} | 同字gid={iS:4d} d={same[iS]:2d}")
