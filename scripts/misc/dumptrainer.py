import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 精确看 0x081C4A00-0x081C4C00 的原版字节（判断是文本还是动画命令）
start = 0x081C4A00 - 0x08000000
end   = 0x081C4C10 - 0x08000000
print("原版字节（0x081C4A00 起，每行16字节）:")
for i in range(start, end, 16):
    addr = 0x08000000 + i
    b = orig[i:i+16]
    print(f'  0x{addr:08X}: {b.hex(" ")}')

print("\n成品字节:")
for i in range(start, end, 16):
    addr = 0x08000000 + i
    b = trans[i:i+16]
    print(f'  0x{addr:08X}: {b.hex(" ")}')
