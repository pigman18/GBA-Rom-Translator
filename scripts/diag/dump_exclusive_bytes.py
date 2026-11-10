import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
with_poke = open('roms/outputs2/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

for addr in (0x080678C8, 0x080678CC, 0x080DF3E8, 0x080DF3EC):
    off = addr - 0x08000000
    o = orig[off:off+4]
    w = with_poke[off:off+4]
    print(f"0x{addr:08X}: 原版={o.hex(' ')}  ->  含图鉴={w.hex(' ')}")

print()
# 精确看 0x080678C8 附近所有字节，理解这 4 个 word 是被当指针还是被当文本改的
print("=== 0x080678B8 - 0x080678E0 字节对比 ===")
lo = 0x080678B8 - 0x08000000
hi = 0x080678E0 - 0x08000000
for i in range(lo, hi, 8):
    addr = 0x08000000 + i
    print(f"  原版: {orig[i:i+8].hex(' ')}")
    print(f"  含图: {with_poke[i:i+8].hex(' ')}")
    print()
