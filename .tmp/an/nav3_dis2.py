import numpy as np
from capstone import *

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
rom = np.fromfile(ROM, dtype=np.uint8)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def dis(a0, n, label=""):
    print("=" * 74)
    print("%s @0x%08X" % (label, a0))
    for i in md.disasm(rom[a0-BASE:a0-BASE+n].tobytes(), a0):
        s = "%08X  %-8s %s" % (i.address, i.mnemonic, i.op_str)
        if i.mnemonic in ("ldr", "str", "ldrh", "strh") and "pc" in i.op_str:
            lit = (i.address + 4) & ~3
            v = int.from_bytes(rom[lit-BASE:lit-BASE+4], "little")
            s += "      ; [0x%08X] = 0x%08X" % (lit, v)
        print("  " + s)

# 2 号调用点所在函数（窗口初始化 + 预取）
dis(0x0806EFC0, 0x90, "site2 窗口初始化（含 SetWindowTileCache / GlyphPrefetchWorker）")
# 1 号调用点所在函数
dis(0x08068580, 0x80, "site1 窗口初始化（base=1）")
# 预取 worker 本体
dis(0x080029E0, 0x70, "GlyphPrefetchWorker")
