import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 图鉴说明唯一改动的 73 字节 0x08384245-0x0838428D，精确看前后上下文
lo = 0x08384230 - 0x08000000
hi = 0x083842A0 - 0x08000000
print("=== 0x08384230-0x083842A0 原版 vs 成品 ===")
for i in range(lo, hi, 16):
    addr = 0x08000000 + i
    o = orig[i:i+16]
    t = trans[i:i+16]
    mark = ' <== 改' if o != t else ''
    print(f"  0x{addr:08X}:")
    print(f"    orig : {o.hex(' ')}")
    print(f"    trans: {t.hex(' ')}{mark}")
