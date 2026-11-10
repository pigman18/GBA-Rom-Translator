import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 找 address 落在动画表区域 0x0837E164-0x0837F4B8 的条目
print("=== address 落在 0x0837E164-0x0837F4B8（动画图片/调色板表）的条目 ===")
found = []
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x0837E164 <= addr <= 0x0837F4B8:
        found.append(e)

print(f"共 {len(found)} 条:")
for e in found[:30]:
    addr = int(str(e.get('address','0')), 16)
    print(f"  0x{addr:08X} module={e.get('module')!r} type={e.get('type')} len={e.get('byte_length')} orig={e.get('original','')[:40]!r}")
