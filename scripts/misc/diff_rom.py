import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

print(f"origin size: {len(orig)} (0x{len(orig):X})")
print(f"trans  size: {len(trans)} (0x{len(trans):X})")

# 对比前 8MB（原版范围）
n = min(len(orig), len(trans))
diffs = []
for i in range(0, n, 4):
    o = struct.unpack_from('<I', orig, i)[0]
    t = struct.unpack_from('<I', trans, i)[0]
    if o != t:
        diffs.append((i, o, t))

print(f"\n原版 8MB 范围内共 {len(diffs)} 个 4 字节字被修改")

# 统计修改分布：按区域归组
from collections import defaultdict
regions = defaultdict(int)
for i, o, t in diffs:
    addr = 0x08000000 + i
    # 粗略分区
    if addr < 0x08010000:
        key = '0x08000000-0x08010000 (text engine)'
    elif addr < 0x08400000:
        key = f'0x08{(addr>>20)&0xFF}xxxxxx (mid)'
    else:
        key = f'0x08{(addr>>20)&0xFF}xxxxxx (data)'
    regions[key] += 1

for k in sorted(regions):
    print(f'  {k}: {regions[k]}')

# 重点：0x08000000-0x08040000 代码区（战斗/文字引擎）的修改
print("\n=== 0x08000000-0x08040000 代码区修改明细 ===")
for i, o, t in diffs:
    addr = 0x08000000 + i
    if addr < 0x08040000:
        print(f'  0x{addr:08X}: {o:08X} -> {t:08X}')
