import struct, json
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 精确扫 0x081C0000-0x081D0000 的 F9 位置，找出"原版无 F9，成品有 F9"的位置
base = 0x081C0000 - 0x08000000
end  = 0x081D0000 - 0x08000000

# 找成品 F9 密集点（原版该处不是 F9 的）
hits = []
for i in range(base, end):
    if trans[i] == 0xF9 and orig[i] != 0xF9:
        hits.append(0x08000000 + i)

# 聚类
clusters = []
for h in hits:
    if clusters and h - clusters[-1][-1] <= 8:
        clusters[-1].append(h)
    else:
        clusters.append([h])

print(f"0x081C0000-0x081D0000 成品新增 F9 共 {len(hits)} 处，聚类 {len(clusters)} 组")
# 只打印地址范围在 0x081c7168 动画脚本表附近的簇
for c in clusters:
    addr = c[0]
    # 动画脚本 gBattleAnims_Moves 英文版 0x081c7168
    if 0x081c6000 <= addr <= 0x081c9000:
        print(f"  簇 @ 0x{addr:08X}-0x{c[-1]:08X} ({len(c)} 字节):")
        for a in c[:8]:
            print(f"    0x{a:08X}: orig=0x{orig[a-0x08000000]:02X} trans=0x{trans[a-0x08000000]:02X}")

# 也查 build.json 里 address 在 0x081c6000-0x081c9000 的 entry
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])
print("\n=== build.json 里 address 在 0x081c6000-0x081c9000 的条目 ===")
for e in entries:
    try:
        addr = int(str(e.get('address','0')), 16)
    except:
        continue
    if 0x081c6000 <= addr <= 0x081c9000:
        print(f"  0x{addr:08X} id={e.get('id')} module={e.get('module')} type={e.get('type')} orig={e.get('original','')!r}")
