import struct
from collections import Counter
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
fixed = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 全面 diff，按段统计，重点看动画/图形数据区
n = min(len(orig), len(fixed))
diffs_by_seg = Counter()
for i in range(0, n, 4):
    if orig[i:i+4] != fixed[i:i+4]:
        diffs_by_seg[(0x08000000+i)>>16] += 1

print("修复后 vs 原版：改动按 64KB 段分布（重点看动画数据区）:")
for seg in sorted(diffs_by_seg):
    print(f"  0x{seg<<16:08X}: {diffs_by_seg[seg]} 处")
