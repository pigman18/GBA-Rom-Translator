import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])
hits = []
for e in entries:
    try:
        addr = int(str(e.get('address', '0')), 16)
    except:
        continue
    if 0x081C4800 <= addr <= 0x081C4C00:
        hits.append((addr, e))

hits.sort()
print(f"动画区 0x081C4800-0x081C4C00 共 {len(hits)} 个条目:")
for addr, e in hits:
    print(f"  0x{addr:08X} id={e.get('id')} module={e.get('module')} "
          f"type={e.get('type')} orig={e.get('original','')!r} "
          f"trans={e.get('translated','')!r}")
