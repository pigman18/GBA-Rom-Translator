import struct, json
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 图鉴说明 scan 范围 0x0837DB9C - 0x08384703
# 英文版动画表 gBattleAnimPicTable @ 0x0837e164, gBattleAnimPaletteTable @ 0x0837ea6c
# 精确对比这个范围内，汉化 ROM 改动了哪些字节

lo = 0x0837DB9C - 0x08000000
hi = 0x08384703 - 0x08000000

diffs = []
for i in range(lo, hi):
    if orig[i] != trans[i]:
        diffs.append(0x08000000 + i)

print(f"图鉴说明范围 0x0837DB9C-0x08384703 共 {hi-lo} 字节，改动 {len(diffs)} 字节")

# 聚类
clusters = []
for h in diffs:
    if clusters and h - clusters[-1][-1] <= 4:
        clusters[-1].append(h)
    else:
        clusters.append([h])

print(f"改动聚类 {len(clusters)} 组:")
for c in clusters:
    print(f"  0x{c[0]:08X} - 0x{c[-1]:08X} ({len(c)} 字节)")

# 重点：是否覆盖 0x0837e164 (动画图片表) 和 0x0837ea6c (调色板表)
print("\n=== 关键动画表地址是否被改动 ===")
for addr, name in ((0x0837e164, 'gBattleAnimPicTable'), (0x0837ea6c, 'gBattleAnimPaletteTable')):
    off = addr - 0x08000000
    o = orig[off:off+16]
    t = trans[off:off+16]
    changed = o != t
    print(f"  {name} @ 0x{addr:08X}: {'改动了!' if changed else '未改动'}")
    print(f"    orig : {o.hex(' ')}")
    print(f"    trans: {t.hex(' ')}")
