"""nav_shift.py — 穷举判定：屏幕格子 == 某个字模的 (横移 dx, 纵移 dy) 版本？
含竖排/换位/16B-32B 错位等所有「单纯读偏」形态。只读。
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

# 竖排版本候选：把字模先转置（若某处按 16x8 布局解释了 8x16 数据）
GTR = np.transpose(GLY, (0, 2, 1))  # (NG,8,16)

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])


def obs(x0, y0):
    band = g[y0:y0 + 16, x0:x0 + 8]
    return (np.abs(band - WHITE).sum(2) > 60)


def shifted(m, dx, dy):
    out = np.zeros_like(m)
    ys = slice(max(0, dy), min(16, 16 + dy))
    xs = slice(max(0, dx), min(8, 8 + dx))
    ys2 = slice(max(0, -dy), min(16, 16 - dy))
    xs2 = slice(max(0, -dx), min(8, 8 - dx))
    out[ys, xs] = m[ys2, xs2]
    return out


print("=== 横移/纵移 穷举（对所有 7168 字取最小） ===")
best_all = []
for label, y0, xs in (("A", 8, (16, 24, 32, 40)),
                      ("B", 24, (16, 24, 32, 72, 80, 128, 136)),
                      ("C", 40, (16, 24, 72, 80, 128, 136))):
    for x0 in xs:
        c = obs(x0, y0)
        if c.sum() == 0:
            continue
        best = (99, None, None, None)
        for dy in range(-8, 9):
            for dx in range(-4, 5):
                s = shifted(c, dx, dy)      # 把屏幕内容反向移回去再比
                d = (GLY != s).reshape(NG, -1).sum(1)
                i = int(d.argmin())
                if d[i] < best[0]:
                    best = (int(d[i]), i, dx, dy)
        # 竖排比对
        cT = np.transpose(c, (1, 0))        # (8,16)
        dT = (GTR != cT).reshape(NG, -1).sum(1)
        iT = int(dT.argmin())
        print(f"{label}{x0:3d} 墨={int(c.sum()):3d} | 平移最优 d={best[0]:2d} "
              f"gid={best[1]} dx={best[2]} dy={best[3]} | 竖排 d={dT[iT]:2d} gid={iT}")
        best_all.append((best[0], f"{label}{x0}"))
print("\n全局最好:", sorted(best_all)[:5])
