import struct
ROM=r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba"
d=open(ROM,'rb').read()
def rd32(a): return struct.unpack_from('<I',d,a-0x08000000)[0]
for a in (0x0806F018,0x0806EFFC,0x0806F000):
    print(f"  *(0x{a:08X}) = 0x{rd32(a):08X}")
print()
# 0x08002C28 是什么
md=None
import capstone
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
print("=== 0x08002C28 起 ===")
for ins in md.disasm(d[0x00002C28:0x00002C28+0x40],0x08002C28):
    print(f"  {ins.address:08X}  {ins.mnemonic:8s} {ins.op_str}")
