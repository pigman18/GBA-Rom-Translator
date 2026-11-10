import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 找 address 在代码区 0x080678xx / 0x080DF3xx 的条目（异常：代码区不该有文本）
targets = [0x080678C8, 0x080678CC, 0x080DF3E8, 0x080DF3EC]
print("=== 涉及被改代码地址的条目 ===")
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    # 看是否覆盖这些代码地址
    blen = int(e.get('byte_length', 0) or 0)
    for t in targets:
        if addr <= t < addr + blen:
            print(f"  entry addr=0x{addr:08X} len={blen} 覆盖 0x{t:08X}")
            print(f"    module={e.get('module')!r} type={e.get('type')} orig={e.get('original','')[:50]!r}")
            print(f"    id={e.get('id')}")
            print()
