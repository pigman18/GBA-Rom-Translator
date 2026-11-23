import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 图鉴说明范围 0x0837DB9C-0x08384703，所有 relocate/hook 条目的 pointer_sources
print("=== 图鉴说明范围条目的 pointer_sources（relocate/hook）===")
cnt = 0
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x0837DB9C <= addr <= 0x08384703:
        ps = e.get('pointer_sources') or e.get('pointer_addresses') or []
        if ps:
            print(f"  text@0x{addr:08X} type={e.get('type')} ptrs={ps}")
            cnt += 1
            if cnt > 40:
                print("  ...(截断)")
                break

print(f"\n共 {cnt} 条有 pointer_sources")
