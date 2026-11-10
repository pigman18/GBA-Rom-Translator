import struct, json
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

base = 0x081C0000 - 0x08000000
end  = 0x081D0000 - 0x08000000

# 找所有 F9 簇，打印完整地址分布
hits = []
for i in range(base, end):
    if trans[i] == 0xF9 and orig[i] != 0xF9:
        hits.append(0x08000000 + i)

clusters = []
for h in hits:
    if clusters and h - clusters[-1][-1] <= 8:
        clusters[-1].append(h)
    else:
        clusters.append([h])

# 按地址排序打印簇的头地址和大小
heads = [(c[0], len(c)) for c in clusters]
heads.sort()
print(f"共 {len(heads)} 簇。前 40 簇的起始地址:")
for addr, n in heads[:40]:
    print(f"  0x{addr:08X}  len={n}")

# 对照 build.json，找这些地址对应哪些模块
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])
# 建立 address -> entry 映射
addr_map = {}
for e in entries:
    try:
        a = int(str(e.get('address','0')), 16)
    except:
        continue
    addr_map[a] = e

print("\n各簇对应的 entry（前 40）:")
for addr, n in heads[:40]:
    e = addr_map.get(addr)
    if e:
        print(f"  0x{addr:08X} module={e.get('module')} type={e.get('type')} orig={e.get('original','')!r}")
    else:
        # 找最近的 entry
        best = None
        for a, ee in addr_map.items():
            if best is None or abs(a - addr) < abs(best - addr):
                best = a
        if best is not None and abs(best - addr) <= 16:
            ee = addr_map[best]
            print(f"  0x{addr:08X} ~附近 0x{best:08X} module={ee.get('module')} type={ee.get('type')}")
        else:
            print(f"  0x{addr:08X} (无对应 entry)")
