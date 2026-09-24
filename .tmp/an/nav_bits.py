"""nav_bits.py — 纯位图检索：屏幕上的 8x8 砖，是否等于字库某个 32B 窗（对齐或滑动）。
只读。
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

LIB = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle_unshadow(0xE0000).bin"
lib = np.frombuffer(open(LIB, "rb").read(), np.uint8)
ST = 128
NG = 7168


def tile_bits_from_bytes(b32):
    """(...,32) -> (...,64) bool，低 nibble 先"""
    lo = (b32 & 0x0F) != 0
    hi = (b32 >> 4) != 0
    out = np.empty(b32.shape[:-1] + (64,), bool)
    out[..., 0::2] = lo
    out[..., 1::2] = hi
    return out


# 对齐砖索引（32B 对齐）
tiles = lib[: (len(lib) // 32) * 32].reshape(-1, 32)
tb = tile_bits_from_bytes(tiles)
keys = {}
for i in range(tb.shape[0]):
    keys.setdefault(tb[i].tobytes(), []).append(i)
print("对齐砖总数", tb.shape[0], " 不同图案", len(keys))

# 滑动窗索引（所有字节偏移）
win = sliding_window_view(lib, 32)
wb = tile_bits_from_bytes(win)
print("滑窗数", wb.shape[0], " (建成)")

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])


def obs(x0, y0):
    band = g[y0:y0 + 16, x0:x0 + 8]
    return (np.abs(band - WHITE).sum(2) > 60)


def find(cell, tag):
    for half, name in ((cell[0:8], "上砖"), (cell[8:16], "下砖")):
        if half.sum() == 0:
            continue
        k = half.reshape(-1).tobytes()
        hit = keys.get(k)
        if hit:
            gids = sorted({(h * 32) // ST for h in hit[:6]})
            print(f"   {tag} {name}: 对齐砖命中 tile={hit[:6]}  ⇒ gid≈{gids}")
        else:
            m = np.all(wb == half.reshape(-1), axis=1)
            idx = np.nonzero(m)[0]
            if idx.size:
                print(f"   {tag} {name}: 滑窗命中 byteoff={idx[:6]} (gid={(idx[0]//ST)}, rem={idx[0]%ST})")
            else:
                # 包含关系：字库里有哪个窗的墨全在屏幕上
                sub = np.logical_and(wb, ~half.reshape(-1)).sum(1)
                j = int(sub.argmin())
                print(f"   {tag} {name}: 未命中；最接近被包含窗 off={j} 差={int(sub[j])}")


for label, y0, xs in (("A", 8, (16, 24, 32, 40)),
                      ("B", 24, (16, 24, 32, 72, 80, 128, 136)),
                      ("C", 40, (16, 24, 72, 80, 128, 136))):
    for x0 in xs:
        c = obs(x0, y0)
        if c.sum() == 0:
            continue
        print(f"\n{label} y{y0} x{x0} 墨={int(c.sum())}")
        find(c, f"{label}{x0}")
