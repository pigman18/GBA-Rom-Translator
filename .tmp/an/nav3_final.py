import numpy as np, os
from capstone import *

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
rom = np.fromfile(ROM, dtype=np.uint8)
N = len(rom)

# ============ (b) 正确的 Thumb BL 扫描 ============
h = rom[:N-4].view(np.uint16).astype(np.uint32)
h0 = h[:-1].astype(np.int64); h1 = h[1:].astype(np.int64)
cand = ((h0 & 0xF800) == 0xF000) & ((h1 & 0xD000) == 0xD000)
idx = np.nonzero(cand)[0]
S = (h0[idx] >> 10) & 1
imm10 = h0[idx] & 0x3FF
J1 = (h1[idx] >> 13) & 1
J2 = (h1[idx] >> 11) & 1
imm11 = h1[idx] & 0x7FF
I1 = 1 - (J1 ^ S)
I2 = 1 - (J2 ^ S)
val = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
val = np.where(val & 0x01000000, val - 0x02000000, val)
addr = BASE + idx * 2
tgt = addr + 4 + val

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
def ctx(a, back=26, fwd=14, label=""):
    print("  --- %s 0x%08X ---" % (label, a))
    o = (a - BASE) - back
    for i in md.disasm(rom[o:(a - BASE) + fwd].tobytes(), BASE + o):
        print("    %08X  %-8s %s%s" % (i.address, i.mnemonic, i.op_str,
                                       " <<<" if i.address == a else ""))

for t, nm in [(0x08002950, "SetWindowTileCache"), (0x08002A50, "InitWindowTileData")]:
    sel = np.nonzero(tgt == t)[0]
    print("=" * 74)
    print("%s @0x%08X  调用点 %d" % (nm, t, len(sel)))
    for k in sel[:8]:
        ctx(int(addr[k]), label=nm)

# ============ (a) 屏幕 64 字节 vs 字库字节位移 ============
FB = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts"
A4 = np.fromfile(os.path.join(FB, "PokeRSFontChsMiddle_unshadow(0xE0000).bin"),
                 dtype=np.uint8)[:7168*128].reshape(7168, 128)

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(int)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)

def obs_pair_bytes(cx, ytop):
    """屏幕 16 行 x 8 px -> 64 字节 4bpp（与字库同编码）"""
    out = bytearray()
    for r in range(16):
        if ytop + r >= ink.shape[0]:
            out += b"\0\0\0\0"; continue
        row = ink[ytop + r, cx:cx+8]
        for c in range(0, 8, 2):
            lo = 0x0F if row[c] else 0x00
            hi = 0xF0 if row[c+1] else 0x00
            out.append(lo | hi)
    return np.frombuffer(bytes(out), dtype=np.uint8)

TARGETS = [("L1x16", 16, 24), ("L1x72", 72, 24), ("L1x128", 128, 24),
           ("L2x16", 16, 40), ("L2x128", 128, 40), ("L2x136", 136, 40)]

print()
print("=" * 74)
print("屏幕砖字节 vs 字库：最佳「逐字节」距离（仅错位/换半，不做位运算）")
for name, cx, ytop in TARGETS:
    O = obs_pair_bytes(cx, ytop).astype(np.int16)
    rec = (10**9, None)
    for gi in range(7168):
        Gb = A4[gi].astype(np.int16)
        for half in (0, 1):
            blk = Gb[half*64:half*64+64] if half else Gb[:64]
            for k in (0, 16, 32, 48):
                cand = np.roll(blk, k)
                d = int(np.abs(cand - O).sum())
                if d < rec[0]:
                    rec = (d, (gi, half, k))
    print("  %-7s 最佳字节距离 %4d  (slot=%d half=%d roll=%d)   [0 = 完全一致]"
          % (name, rec[0], rec[1][0], rec[1][1], rec[1][2]))
