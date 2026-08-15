import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 找 address 落在 EWRAM (0x02000000-0x02040000) 或 IWRAM (0x03000000) 的条目
print("=== build.json 里 EWRAM/IWRAM 地址的条目 ===")
cnt = 0
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x02000000 <= addr <= 0x02040000 or 0x03000000 <= addr <= 0x03008000:
        print(f"  0x{addr:08X} id={e.get('id')} module={e.get('module')} type={e.get('type')} orig={e.get('original','')[:30]!r}")
        cnt += 1
        if cnt > 40:
            print("  ...(更多)")
            break

print(f"\n共 {cnt} 条（截断显示）")
