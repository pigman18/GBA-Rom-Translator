import numpy as np, os
from capstone import *

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
rom = np.fromfile(ROM, dtype=np.uint8)

print("#" * 74)
print("# A) 解析 0x0806EFC0 与 0x08068580 区块里所有 PC 相对字面量")
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for a0, n in ((0x0806EFC0, 0x80), (0x080685A0, 0x50)):
    print("-" * 74)
    for i in md.disasm(rom[a0-BASE:a0-BASE+n].tobytes(), a0):
        mn = i.mnemonic
        if mn in ("ldr", "str", "ldrh", "strh", "add") and "[pc" in i.op_str:
            imm = int(i.op_str.split("#")[1].rstrip("]"), 16)
            lit = ((i.address + 4) & ~3) + imm
            v = int.from_bytes(rom[lit-BASE:lit-BASE+4], "little")
            print("  %08X %-7s %-22s -> lit 0x%08X = 0x%08X" % (i.address, mn, i.op_str, lit, v))

print()
print("#" * 74)
print("# B) 屏幕砖 vs 最佳字库字的逐字节对照（L1x128）")
A4 = np.fromfile(os.path.join(r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts",
                              "PokeRSFontChsMiddle_unshadow(0xE0000).bin"),
                 dtype=np.uint8)[:7168*128].reshape(7168, 128)
g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(int)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)

def obs_pair_bytes(cx, ytop):
    out = bytearray()
    for r in range(16):
        row = ink[ytop + r, cx:cx+8]
        for c in range(0, 8, 2):
            out.append((0x0F if row[c] else 0) | (0xF0 if row[c+1] else 0))
    return np.frombuffer(bytes(out), dtype=np.uint8)

def show64(blk, label):
    print("  %s" % label)
    for r in range(16):
        line = ""
        for b in blk[r*4:r*4+4]:
            line += "#" if (b & 0x0F) else "."
            line += "#" if (b >> 4) else "."
        print("    %s" % line)

for name, cx, ytop, gi in (("L1x128", 128, 24, 7028), ("L1x16", 16, 24, 4148)):
    O = obs_pair_bytes(cx, ytop)
    Gb = A4[gi][:64]
    print("-" * 74)
    print("%s  vs slot %d" % (name, gi))
    print("  obs hex:", O.tobytes().hex())
    print("  lib hex:", Gb.tobytes().hex())
    diff = np.nonzero(O != Gb)[0]
    print("  不同字节下标:", diff.tolist())
    print("  obs 值/ lib 值:", [(hex(int(O[k])), hex(int(Gb[k]))) for k in diff[:12]])
    show64(Gb, "字库 slot %d 前 64B" % gi)
    show64(O, "屏幕砖 (y%d..%d, x%d)" % (ytop, ytop+15, cx))
