import numpy as np, os

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
NG = 7168
rom = np.fromfile(ROM, dtype=np.uint8)
print("ROM", len(rom))

# hook 区核对
gamebin = np.fromfile(r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook\out\game.bin", dtype=np.uint8)
off = 0x08800000 - BASE
seg = rom[off:off+len(gamebin)]
print("hook 区与当前 out/game.bin 逐字节相同:", np.array_equal(seg, gamebin),
      " (%d B)" % len(gamebin))

def grab(addr, n):
    o = addr - BASE
    return rom[o:o+n].copy()

# 4bpp
A4 = grab(0x09400000, NG*128).reshape(NG, 128)
px = np.zeros((NG, 128, 2), np.uint8)
px[:, :, 0] = (A4 & 0x0F) != 0
px[:, :, 1] = (A4 >> 4) != 0
G4 = px.reshape(NG, 16, 16)
# 1bpp
B1 = grab(0x09700000, NG*13)
bits = np.unpackbits(B1.reshape(NG, 13), axis=1, bitorder="big")
G1 = bits[:, :99].reshape(NG, 11, 9)

# 与工作区 bin 对比
W4 = np.fromfile(r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle_unshadow(0xE0000).bin", dtype=np.uint8)[:NG*128]
print("ROM 4bpp == 工作区 bin:", np.array_equal(A4.reshape(-1), W4))
W1 = np.fromfile(r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle1Bpp_unshadow(0x16C00).bin", dtype=np.uint8)[:NG*13]
print("ROM 1bpp == 工作区 bin:", np.array_equal(B1.reshape(-1), W1))

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(int)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)

def show(obs, lib, dx, name, mirror=False):
    print("    %-22s | %s" % (name, "obs(cell)"))
    for r in range(obs.shape[0]):
        o = "".join("#" if obs[r, c] else "." for c in range(8))
        l = "".join("#" if lib[r, c] else "." for c in range(8))
        x = "".join("X" if (obs[r, c] != lib[r, c]) else "." for c in range(8))
        print("    %-22s | %s  diff %s" % (l, o, x))

# 以 L1@16 为例：4bpp 库最佳
S = ink[26:37, 16:24].astype(np.uint8)
d4 = np.abs(G4[:, 2:13, 0:8].reshape(NG, -1).astype(np.int16) - S.reshape(-1).astype(np.int16)).sum(axis=1)
i4 = int(np.argmin(d4))
print()
print("=== L1@16  4bpp 最佳 slot=%d d=%d ===" % (i4, d4[i4]))
show(S, G4[i4, 2:13, 0:8].astype(bool), 0, "lib4bpp(rows2-12)")

d1 = np.abs(G1.reshape(NG, -1).astype(np.int16) - S[:, :8].reshape(-1)[:99].astype(np.int16)).sum(axis=1)
i1 = int(np.argmin(d1))
print()
print("=== L1@16  1bpp 9x11 最佳 slot=%d d=%d ===" % (i1, d1[i1]))
for r in range(11):
    o = "".join("#" if S[r, c] else "." for c in range(8))
    l = "".join("#" if G1[i1, r, c] else "." for c in range(9))
    print("    %-10s | %s" % (l, o))
