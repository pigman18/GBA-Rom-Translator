import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# ProcessCurrentChar hook 区域 0x08003360 - 0x08003390
start = 0x08003360
end = 0x08003390
print("=== ProcessCurrentChar hook 区域对比 ===")
for addr in range(start, end, 2):
    off = addr - 0x08000000
    o = struct.unpack_from('<H', orig, off)[0]
    t = struct.unpack_from('<H', trans, off)[0]
    mark = '  <== 改' if o != t else ''
    print(f'  0x{addr:08X}: orig={o:04X} trans={t:04X}{mark}')

# 精确看 hook 字节
print("\n=== hook 机器码解读 ===")
# trans 0x0800336C 起
for addr in range(0x0800336C, 0x08003380, 2):
    off = addr - 0x08000000
    t = struct.unpack_from('<H', trans, off)[0]
    print(f'  0x{addr:08X}: {t:04X}')

# ProcessCurrentChar 0x080032F8 完整函数（看 RegularGlyph 0x0800336E 在哪）
print("\n=== ProcessCurrentChar @ 0x080032F8（前 60 半字）===")
for addr in range(0x080032F8, 0x08003370, 2):
    off = addr - 0x08000000
    o = struct.unpack_from('<H', orig, off)[0]
    print(f'  0x{addr:08X}: {o:04X}')
