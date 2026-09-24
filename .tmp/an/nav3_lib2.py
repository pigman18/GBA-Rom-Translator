import numpy as np, os

FD = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts"
F4 = os.path.join(FD, "PokeRSFontChsMiddle_unshadow(0xE0000).bin")
F4b = os.path.join(FD, "PokeRSFontChsMiddle(0xE0000).bin")
F1 = os.path.join(FD, "PokeRSFontChsMiddle1Bpp_unshadow(0x16C00).bin")

def load(p):
    return np.fromfile(p, dtype=np.uint8), os.path.getsize(p)

L4, s4 = load(F4)
L4b, s4b = load(F4b)
L1, s1 = load(F1)
print("4bpp unshadow %d B -> %d chars @128" % (s4, s4//128))
print("4bpp shadow   %d B -> %d chars @128" % (s4b, s4b//128))
print("1bpp unshadow %d B -> %d chars @13" % (s1, s1//13))
print("4bpp == shadow-version:", np.array_equal(L4, L4b))

def pack(lead, trail):
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return (idx << 8) | trail

def dec_4bpp_row4(blk4):
    s = ""
    for b in blk4:
        s += "#" if (b & 0x0F) else "."
        s += "#" if (b >> 4) else "."
    return s

print()
print("############ 4bpp Middle: 每字 128B 的「唯一字节值」统计 ############")
u = np.unique(L4)
print("全库唯一字节值:", u[:40], "... 共", len(u))
# 全库：每 128B 里前 64 / 后 64 的非零字节数
A = L4[:(len(L4)//128)*128].reshape(-1, 128)
print("前64B 非零总数 =", np.count_nonzero(A[:, :64]))
print("后64B 非零总数 =", np.count_nonzero(A[:, 64:]))
print("有墨字数(前64非零>0) =", np.count_nonzero(A[:, :64].any(axis=1)))
print("有墨字数(后64非零>0) =", np.count_nonzero(A[:, 64:].any(axis=1)))
# 四个 32B 块
for i, (a, b) in enumerate([(0,32),(32,64),(64,96),(96,128)]):
    print("块%d (bytes %d..%d) 非零 = %d, 有墨字数 = %d" %
          (i, a, b, np.count_nonzero(A[:, a:b]), np.count_nonzero(A[:, a:b].any(axis=1))))

for name, (ld, tr) in [("领", (0x08, 0xBF)), ("航", (0x04, 0xE3)),
                       ("员", (0x0F, 0xBD)), ("宝", (0x01, 0x63))]:
    g = pack(ld, tr)
    blk = L4[g*128:(g+1)*128]
    print()
    print("="*78)
    print("%s  gid=%d" % (name, g))
    print(" hex 0..31  :", blk[0:32].tobytes().hex())
    print(" hex 32..63 :", blk[32:64].tobytes().hex())
    print(" hex 64..95 :", blk[64:96].tobytes().hex())
    print(" hex 96..127:", blk[96:128].tobytes().hex())
    print(" -- 解1: 前64B 按 4bpp 8宽x16高（块0=上砖, 块1=下砖）--")
    for r in range(8):
        print("   %s" % dec_4bpp_row4(blk[r*4:r*4+4]))
    for r in range(8):
        print("   %s" % dec_4bpp_row4(blk[32+r*4:32+r*4+4]))
    print(" -- 解2: 每字节=1像素(低nibble)，8宽x16高 --")
    for r in range(16):
        print("   %s" % "".join("#" if blk[r*8+c] else "." for c in range(8)))
