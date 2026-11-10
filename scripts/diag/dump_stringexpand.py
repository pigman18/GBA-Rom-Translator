import struct

orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# StringExpandPlaceholders 完整范围 0x08004530 - 0x080045C8
start = 0x08004530
end   = 0x080045D0

print("=== StringExpandPlaceholders 完整 (0x08004530-0x080045D0) 对比 ===")
off_s = start - 0x08000000
off_e = end - 0x08000000
for addr in range(start, end, 2):
    off = addr - 0x08000000
    o = struct.unpack_from('<H', orig, off)[0]
    t = struct.unpack_from('<H', trans, off)[0]
    mark = '  <== 被修改' if o != t else ''
    print(f'  0x{addr:08X}: orig={o:04X}  trans={t:04X}{mark}')

print("\n=== 跳转表字面量（原版，每2字节）===")
# 0x08004544 附近的 ldr 池
for addr in range(0x08004540, 0x08004568, 4):
    off = addr - 0x08000000
    w = struct.unpack_from('<I', orig, off)[0]
    print(f'  0x{addr:08X}: 0x{w:08X}')
