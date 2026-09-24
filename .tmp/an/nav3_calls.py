import numpy as np
from capstone import *

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
rom = np.fromfile(ROM, dtype=np.uint8)
N = len(rom)

h = rom[:N-3].view(np.uint16).astype(np.uint32)   # 每个偶数偏移的 u16（小端）
h0 = h[:-2]
h1 = h[1:-1]
cand = ((h0 & 0xF800) == 0xF000) & ((h1 & 0xD000) == 0xD000)
idx = np.nonzero(cand)[0]
print("候选 BL 数:", len(idx))

s = ((h0[idx] >> 10) & 1).astype(np.int64)
imm = (h0[idx] & 0x7FF).astype(np.int64)
j2 = ((h1[idx] >> 11) & 1).astype(np.int64)
j1 = ((h1[idx] >> 13) & 1).astype(np.int64)
imm2 = (h1[idx] & 0x7FF).astype(np.int64)
val = (s << 24) | (j1 << 23) | (j2 << 22) | (imm << 12) | (imm2 << 1)
val = np.where(val & 0x01000000, val - 0x02000000, val)
addr = BASE + idx.astype(np.int64) * 2
tgt = addr + 4 + val

TARGETS = {0x08002950: "SetWindowTileCache", 0x08002A50: "InitWindowTileData",
           0x080029E0: "GlyphPrefetchWorker", 0x08002C68: "InitTextPrinter"}
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def ctx(a, back=24, fwd=20):
    o = (a - BASE) - back
    code = rom[o:(a - BASE) + fwd].tobytes()
    for i in md.disasm(code, BASE + o):
        mark = " <<<" if i.address == a else ""
        print("    %08X  %-8s %s%s" % (i.address, i.mnemonic, i.op_str, mark))

for t, name in TARGETS.items():
    sel = np.nonzero(tgt == t)[0]
    print("=" * 76)
    print("%s @0x%08X  调用点 %d 个" % (name, t, len(sel)))
    for k in sel[:6]:
        a = int(addr[k])
        print("  --- caller near 0x%08X ---" % a)
        ctx(a)
