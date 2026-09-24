import numpy as np
from capstone import *

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000
rom = np.fromfile(ROM, dtype=np.uint8)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = False

def dis(addr, n, label=""):
    o = addr - BASE
    code = rom[o:o+n].tobytes()
    print("=" * 72)
    print("%s  @0x%08X  (%d B)" % (label, addr, n))
    for i in md.disasm(code, addr):
        print("  %08X  %-8s %s" % (i.address, i.mnemonic, i.op_str))

dis(0x08002950, 0x40, "SetWindowTileCache")
dis(0x08002A50, 0x50, "InitWindowTileData")
