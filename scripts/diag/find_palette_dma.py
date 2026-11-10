import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

# 搜索 palette RAM 基址 0x05000000 作为字面量（DMA 目标），或 0x05000000 附近
needle = struct.pack('<I', 0x05000000)
targets = []
start = 0
while True:
    j = rom.find(needle, start)
    if j < 0: break
    targets.append(j)
    start = j + 1

print(f"ROM 里字面量 0x05000000 (palette RAM) 出现 {len(targets)} 处:")
for j in targets:
    print(f"  0x{0x08000000+j:08X}")

# 也搜 0x040000D4 (DMA3 源寄存器) 和 0x040000D0/D8 等 DMA 寄存器
for val, name in ((0x040000D0, 'DMA0SAD'), (0x040000D4, 'DMA3SAD'), (0x040000DC, 'DMA3CNT')):
    n = struct.pack('<I', val)
    hits = []
    s = 0
    while True:
        j = rom.find(n, s)
        if j < 0: break
        hits.append(0x08000000+j)
        s = j+1
    if hits:
        print(f"{name} (0x{val:08X}) 字面量 {len(hits)} 处: {[f'0x{h:08X}' for h in hits[:10]]}")
