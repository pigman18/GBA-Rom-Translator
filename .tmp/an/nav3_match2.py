import numpy as np, os

FD = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts"
F4 = os.path.join(FD, "PokeRSFontChsMiddle_unshadow(0xE0000).bin")
F1 = os.path.join(FD, "PokeRSFontChsMiddle1Bpp_unshadow(0x16C00).bin")
NG = 7168

# ---- 4bpp 8x16 ----
A = np.fromfile(F4, dtype=np.uint8)[:NG*128].reshape(NG, 128)
px = np.zeros((NG, 128, 2), np.uint8)
px[:, :, 0] = (A & 0x0F) != 0
px[:, :, 1] = (A >> 4) != 0
G4 = px.reshape(NG, 16, 16)          # 16 行 x 16 px（左 8 px 有墨）
del A, px

# ---- 1bpp 9x11 MSB-first, row-major, no padding ----
B = np.fromfile(F1, dtype=np.uint8)
NB = len(B) // 13
print("1bpp chars =", NB)
bits = np.unpackbits(B[:NB*13].reshape(NB, 13), axis=1, bitorder="big")  # (NB,104)
M = bits[:, :99].reshape(NB, 11, 9)                                      # 9 宽 x 11 高

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(int)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)

# 目标：16 px 宽的墨迹带（两格），11 行
def strip(x0, y0):
    return ink[y0:y0+11, x0:x0+16].astype(np.uint8)

STRIPS = [("L1@16", strip(16, 26)), ("L1@72", strip(72, 26)),
          ("L1@128", strip(128, 26)), ("L2@16", strip(16, 42)),
          ("L2@80", strip(80, 42)), ("L2@128", strip(128, 42))]

def best_in_lib(libname, imgs, W):
    print("### 库 %s（字宽 %d）" % (libname, W))
    for name, S in STRIPS:
        rec = (10**9, None)
        for dx in range(0, 16 - W + 1):
            t = S[:, dx:dx+W].reshape(-1).astype(np.int16)
            for mirror in (0, 1):
                Mx = imgs[:, :, ::-1] if mirror else imgs
                D = np.abs(Mx.reshape(imgs.shape[0], -1).astype(np.int16) - t).sum(axis=1)
                i = int(np.argmin(D))
                if D[i] < rec[0]:
                    rec = (int(D[i]), (i, "mh" if mirror else "id", dx))
        print("  %-8s ink=%3d  best d=%3d  slot=%5d %s dx=%d"
              % (name, S.sum(), rec[0], rec[1][0], rec[1][1], rec[1][2]))
    print()

best_in_lib("Middle 4bpp 8x16", G4[:, 2:13, 0:8], 8)
best_in_lib("Middle 1bpp 9x11", M.astype(np.uint8), 9)
