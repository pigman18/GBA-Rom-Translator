import json
from collections import defaultdict
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 按模块统计 in_place 和 relocate 条目的地址段分布
seg_hist = defaultdict(int)
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    seg = addr >> 16
    seg_hist[seg] += 1

print("所有条目地址按 64KB 段分布:")
for seg in sorted(seg_hist):
    print(f"  0x{seg<<16:08X}: {seg_hist[seg]} 条")

# 重点：找地址落在 0x0837xxxx（英文版动画图片/调色板表区）的条目
print("\n=== 地址在 0x08370000-0x08380000 的条目（英文版动画表区）===")
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x08370000 <= addr <= 0x08380000:
        print(f"  0x{addr:08X} id={e.get('id')} module={e.get('module')} type={e.get('type')} orig={e.get('original','')[:20]!r}")
