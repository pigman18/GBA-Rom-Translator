import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 找成品 ROM 里"原版含 F9(0xF9) 但成品不含"或"成品新增 F9"的位置。
# 更关键：找动画脚本数据区。英文版 gBattleAnims 在 0x081c7168-0x081c7778+。
# 日版偏移未知，但动画脚本命令流有特征：以 0x00-0x0F 命令字节开头，后跟参数。

# 方法：扫描成品 ROM 里 F9 字节密集、且原版该处是"命令流模式"(小字节)的区域。
# 简化：统计成品 ROM 里 F9 字节的分布（按 0x10000 段），找异常密集段。

from collections import Counter
seg_counter = Counter()
for i, b in enumerate(trans):
    if b == 0xF9:
        seg = (0x08000000 + i) >> 16
        seg_counter[seg] += 1

print("成品 ROM 里 F9 字节按 64KB 段分布（Top 30）:")
for seg, cnt in seg_counter.most_common(30):
    print(f'  0x{seg<<16:08X}-0x{(seg<<16)+0xFFFF:08X}: {cnt} 个 F9')
