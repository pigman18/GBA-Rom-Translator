import numpy as np

BIN = r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\fonts\Middle.bin"
import os, glob
cands = glob.glob(r"C:\code\GBA-Rom-Translator\**\Middle.bin", recursive=True)
print("candidates:")
for c in cands[:20]:
    print("  ", c, os.path.getsize(c))

# 找到真正的字库
lib = None
for c in cands:
    if os.path.getsize(c) == 917504:
        lib = c
        break
if lib is None:
    for c in cands:
        s = os.path.getsize(c)
        if s % 128 == 0 and s > 100000:
            lib = c
            break
print("USING", lib, os.path.getsize(lib))
L = np.fromfile(lib, dtype=np.uint8)
N = len(L) // 128
print("chars", N)
L = L[:N*128].reshape(N, 128)

def pack(lead, trail):
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return (idx << 8) | trail

def show4bpp(blk, label):
    # blk: bytes, 按 8x8 砖逐行解码，4bpp
    print("  %s" % label)
    for r in range(len(blk)//4):
        row = blk[r*4:r*4+4]
        s = ""
        for b in row:
            s += "#" if (b & 0x0F) else "."
            s += "#" if (b >> 4) else "."
        print("    %s" % s)

for name, (ld, tr) in [("领", (0x08, 0xBF)), ("航", (0x04, 0xE3)),
                       ("员", (0x0F, 0xBD)), ("宝", (0x01, 0x63))]:
    g = pack(ld, tr)
    blk = L[g]
    nz = np.count_nonzero(blk)
    print("="*70)
    print("%s gid=%d  非零字节=%d/128" % (name, g, nz))
    print("  前 64 字节 hex:", blk[:32].tobytes().hex())
    print("                ", blk[32:64].tobytes().hex())
    print("  后 64 字节 hex:", blk[64:96].tobytes().hex())
    print("                ", blk[96:128].tobytes().hex())
    print("  唯一字节值:", sorted(set(blk.tolist()))[:20])
    # 按「前64字节 = 8x16」解
    show4bpp(blk[:64], "前64字节按 8宽x16高 解 (块0=上砖, 块1=下砖)")
    # 按「128字节 = 16x16」解 (TL,TR,BL,BR)
    print("  128字节按 16x16 解 (TL/TR/BL/BR):")
    for r in range(8):
        s = ""
        for t in (0, 1):
            for b in blk[t*32 + r*4: t*32 + r*4 + 4]:
                s += "#" if (b & 0x0F) else "."
                s += "#" if (b >> 4) else "."
        print("    %s" % s)
