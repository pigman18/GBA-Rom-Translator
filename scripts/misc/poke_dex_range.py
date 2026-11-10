import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])
# 找出 address 在 0x0837D000-0x08380000 的所有 entry，统计 module 和 type
from collections import Counter
mods = Counter()
types = Counter()
addr_min = 0xFFFFFFFF
addr_max = 0
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x08370000 <= addr <= 0x08380000:
        mods[e.get('module')] += 1
        types[e.get('type')] += 1
        addr_min = min(addr_min, addr)
        addr_max = max(addr_max, addr)

print(f"0x0837xxxx 区域:")
print(f"  地址范围: 0x{addr_min:08X} - 0x{addr_max:08X}")
print(f"  模块分布: {dict(mods)}")
print(f"  类型分布: {dict(types)}")
