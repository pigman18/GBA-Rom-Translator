import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 英文版动画表区域 0x0837e164-0x0837f4b8（pic 0x909*4 + palette 0x909*4 + bg）
# 日版可能偏移，但先扫这个区域看有没有 F9 污染 / 指针被改
lo = 0x0837e000 - 0x08000000
hi = 0x0837f600 - 0x08000000

# 找这个区域里，成品 vs 原版的差异，特别是含 F9 的
diffs = []
for i in range(lo, hi, 4):
    o = struct.unpack_from('<I', orig, i)[0]
    t = struct.unpack_from('<I', trans, i)[0]
    if o != t:
        diffs.append((0x08000000+i, o, t))

print(f"0x0837E000-0x0837F600 区域差异数: {len(diffs)}")
for addr, o, t in diffs[:60]:
    print(f"  0x{addr:08X}: orig=0x{o:08X} trans=0x{t:08X}")

# 也检查这段区域原版是否是指针表（含 0x08xxxxxx 指针）
print("\n=== 原版 0x0837e164 (gBattleAnimPicTable) 前 10 个条目 ===")
base = 0x0837e164 - 0x08000000
for i in range(10):
    w = struct.unpack_from('<I', orig, base + i*4)[0]
    w2 = struct.unpack_from('<I', trans, base + i*4)[0]
    mark = ' <== 改' if w != w2 else ''
    print(f"  [{i}] 0x{w:08X} -> 0x{w2:08X}{mark}")
