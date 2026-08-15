import json
from collections import defaultdict
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 收集所有 in_place 条目地址（按模块分组）
by_mod = defaultdict(list)
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if e.get('type') == 'in_place':
        by_mod[e.get('module')].append(addr)

print("各模块 in_place 地址范围:")
for mod, addrs in sorted(by_mod.items()):
    addrs.sort()
    if addrs:
        print(f"  {mod}: {len(addrs)} 条, 0x{addrs[0]:08X} - 0x{addrs[-1]:08X}")

# 找地址落在 0x08150000-0x081BFFFF 或 0x081D0000-0x081FFFFF 的 in_place（疑似动画区）
print("\n=== in_place 地址落在疑似动画脚本区(0x0815-0x081B, 0x081D-0x081F) 的条目 ===")
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if e.get('type') != 'in_place':
        continue
    if (0x08150000 <= addr <= 0x081BFFFF) or (0x081D0000 <= addr <= 0x081FFFFF):
        print(f"  0x{addr:08X} id={e.get('id')} module={e.get('module')} orig={e.get('original','')!r}")
