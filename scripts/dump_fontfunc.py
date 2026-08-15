import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# FontFuncTable @ 0x081BB3AC，读 8 个条目（32 字节）
print("=== FontFuncTable @ 0x081BB3AC（8 个函数指针）===")
for i in range(8):
    off = 0x081BB3AC - 0x08000000 + i*4
    o = struct.unpack_from('<I', orig, off)[0]
    t = struct.unpack_from('<I', trans, off)[0]
    mark = '  <== 改' if o != t else ''
    print(f'  [{i}] orig=0x{o:08X} trans=0x{t:08X}{mark}')

# CallVia 跳板 0x081B12D4-0x081B12E0
print("\n=== CallVia 跳板 @ 0x081B12D4-0x081B12E4 ===")
for addr in range(0x081B12D4, 0x081B12E4, 2):
    off = addr - 0x08000000
    o = struct.unpack_from('<H', orig, off)[0]
    t = struct.unpack_from('<H', trans, off)[0]
    mark = '  <== 改' if o != t else ''
    print(f'  0x{addr:08X}: orig={o:04X} trans={t:04X}{mark}')
