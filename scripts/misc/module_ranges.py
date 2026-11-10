import json
from collections import defaultdict
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 按模块统计地址范围
ranges = defaultdict(lambda: [0xFFFFFFFF, 0])
counts = defaultdict(int)
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    m = e.get('module')
    counts[m] += 1
    ranges[m][0] = min(ranges[m][0], addr)
    ranges[m][1] = max(ranges[m][1], addr)

print("各模块地址范围（按起始地址排序）:")
for m in sorted(ranges, key=lambda x: ranges[x][0]):
    lo, hi = ranges[m]
    print(f"  {m!r}: {counts[m]} 条, 0x{lo:08X} - 0x{hi:08X}")
