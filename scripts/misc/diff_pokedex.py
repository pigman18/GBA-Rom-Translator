import struct
from collections import Counter

no_poke = open('roms/outputs/POKEMON_RUBY_AXVJ00_nopoke.gba','rb').read()  # 不含图鉴说明
with_poke = open('roms/outputs2/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()  # 含图鉴说明

# diff 两 ROM，找出图鉴说明导致的额外改动
n = min(len(no_poke), len(with_poke))
diffs = []
for i in range(0, n, 4):
    a = struct.unpack_from('<I', no_poke, i)[0]
    b = struct.unpack_from('<I', with_poke, i)[0]
    if a != b:
        diffs.append(0x08000000 + i)

print(f"图鉴说明导致额外改动 {len(diffs)} 个 4 字节字")

# 按段分布
seg = Counter()
for addr in diffs:
    seg[addr >> 16] += 1
print("\n按 64KB 段分布:")
for s in sorted(seg):
    print(f"  0x{s<<16:08X}: {seg[s]} 处")

# 重点：代码区 0x08000000-0x08100000 的改动
print("\n=== 代码区 0x0800xxxx-0x0810xxxx 的改动 ===")
code_diffs = [a for a in diffs if 0x08000000 <= a <= 0x08100000]
for a in code_diffs[:60]:
    off = a - 0x08000000
    print(f"  0x{a:08X}: 无图鉴=0x{struct.unpack_from('<I',no_poke,off)[0]:08X} 有图鉴=0x{struct.unpack_from('<I',with_poke,off)[0]:08X}")
