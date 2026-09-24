import numpy as np, os

FD = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts"
L4 = np.fromfile(os.path.join(FD, "PokeRSFontChsMiddle_unshadow(0xE0000).bin"), dtype=np.uint8)
NG = 7168
A = L4[:NG*128].reshape(NG, 128)
px = np.zeros((NG, 128, 2), dtype=np.uint8)
px[:, :, 0] = (A & 0x0F) != 0
px[:, :, 1] = (A >> 4) != 0
G16 = px.reshape(NG, 16, 16).astype(np.uint8)   # 16 行 x 16 px

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(int)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)

def cell(cx, y0, nrow=11):
    return ink[y0:y0+nrow, cx:cx+8].astype(np.uint8)

TARGETS = [("L1x16", cell(16, 26)), ("L1x72", cell(72, 26)),
           ("L1x80", cell(80, 26)), ("L1x128", cell(128, 26)),
           ("L1x136", cell(136, 26)),
           ("L2x16", cell(16, 42)), ("L2x96", cell(96, 42)),
           ("L2x128", cell(128, 42)), ("L2x136", cell(136, 42))]

def w8(x):
    return x[:, :, :8]

VAR, VN = [], []
for half, x0 in (("L", 0), ("R", 8)):
    sub = G16[:, :, x0:x0+8]                      # (NG,16,8)
    VAR.append(sub);                              VN.append("id_" + half)
    VAR.append(sub[:, :, ::-1]);                  VN.append("mh_" + half)
    VAR.append(w8(np.repeat(sub, 2, axis=2)));    VN.append("sx2_" + half)
    sp = np.zeros((NG, 16, 16), np.uint8); sp[:, :, 0::2] = sub
    VAR.append(w8(sp));                           VN.append("sp_" + half)
    VAR.append(np.repeat(sub, 2, axis=1)[:, :16]);   VN.append("sy2_" + half)
    V2 = np.repeat(sub, 2, axis=1)[:, :16]
    VAR.append(w8(np.repeat(V2, 2, axis=2)));     VN.append("sxsy_" + half)

V = np.stack(VAR, axis=0)                          # (nvar, NG, 16, 8)
NV = V.shape[0]
print("variants", NV, V.shape)
del VAR

for name, T in TARGETS:
    t = T.reshape(-1).astype(np.int16)
    rec = (10**9, None)
    for dy in range(0, 16-11+1):
        S = V[:, :, dy:dy+11, :].reshape(NV, NG, -1).astype(np.int16)
        D = np.abs(S - t).sum(axis=2)
        idx = np.unravel_index(np.argmin(D), D.shape)
        d = int(D[idx])
        if d < rec[0]:
            rec = (d, (int(idx[1]), VN[idx[0]], dy))
    print("%-7s ink=%3d  best d=%3d  glyph=%5d var=%-9s dy=%d"
          % (name, T.sum(), rec[0], rec[1][0], rec[1][1], rec[1][2]))
