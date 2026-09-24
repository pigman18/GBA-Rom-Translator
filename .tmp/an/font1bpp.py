import struct, numpy as np, capstone
ROM=r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
JROM=r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba"
d=open(ROM,'rb').read()
def rd32(a): return struct.unpack_from('<I',d,a-0x08000000)[0]
print("=== DrawGlyphTiles 字模表 0x08003678 ===")
for i in range(8):
    v=rd32(0x08003678+i*4)
    print(f"   [{i}] 0x{v:08X}")
print()
print("=== 0x081B49AC / 0x081B51AC 指向 ===")
for a in (0x081B49AC,0x081B51AC):
    print(f"   *(0x{a:08X}) = 0x{rd32(a):08X}   *(0x{a+4:08X}) = 0x{rd32(a+4):08X}")
print()
print("=== 字体源区几何 ===")
for base,label,per in ((0x09000000,"Normal 4bpp",128),(0x09100000,"Small 4bpp",128),
                       (0x09400000,"Middle 4bpp",128),(0x09500000,"Big1bpp?",16),
                       (0x09600000,"Small1bpp?",11),(0x09700000,"Middle1bpp?",13)):
    try:
        seg=d[base-0x08000000: base-0x08000000+per*8]
        nz=sum(1 for b in seg if b)
        print(f"   0x{base:08X} {label:12s} 首 {per*8} 字节非零 {nz}")
    except Exception as e: print("   ",base,e)
