import json
from collections import Counter
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 收集所有 relocate/hook 条目的 pointer_sources，按段统计
seg = Counter()
all_ptrs = []
for e in entries:
    if e.get('type') not in ('relocate','hook'):
        continue
    mod = e.get('module')
    for p in (e.get('pointer_sources') or []):
        try:
            pa = int(str(p).replace('0x',''), 16)
        except:
            continue
        seg[pa >> 16] += 1
        all_ptrs.append((pa, mod))

print("relocate/hook 的 pointer_sources 按段分布:")
for s in sorted(seg):
    print(f"  0x{s<<16:08X}: {seg[s]} 处")

# 重点：动画数据区（0x08d0xxxx 英文版动画图片，日版可能不同）
# 找落在 0x08300000-0x08400000 或 0x08d00000-0x08e00000 的指针源
print("\n=== 落在疑似动画/图形数据区的 pointer_sources ===")
for pa, mod in all_ptrs:
    if (0x08300000 <= pa <= 0x08400000) or (0x08c00000 <= pa <= 0x08e00000):
        print(f"  0x{pa:08X} module={mod!r}")
