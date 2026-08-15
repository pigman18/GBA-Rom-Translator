import json
from collections import Counter
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

types = Counter()
total = 0
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x0837DB9C <= addr <= 0x08384703:
        types[e.get('type')] += 1
        total += 1

print(f"图鉴说明范围条目总数: {total}")
print(f"type 分布: {dict(types)}")

# 列出 relocate 和 hook 类型的
print("\n=== relocate/hook 类型条目详情 ===")
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x0837DB9C <= addr <= 0x08384703 and e.get('type') in ('relocate','hook'):
        print(f"  0x{addr:08X} type={e.get('type')} module={e.get('module')!r} ps={e.get('pointer_sources')} orig={e.get('original','')[:30]!r}")
