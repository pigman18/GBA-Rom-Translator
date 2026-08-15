import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# RunTextPrinter @ 0x08002DE8
for addr in (0x08002DE8, 0x08002DE0, 0x08002E00):
    off = addr - 0x08000000
    print(f'{addr:08X}:')
    print('  origin:', orig[off:off+32].hex(' '))
    print('  trans :', trans[off:off+32].hex(' '))
    print()

# 搜索原版里所有引用 .word 0x08002DE9（Thumb）或 0x08002DE8 的位置
print("=== 原版中引用 0x08002DE8/0x08002DE9 的指针 ===")
needle_thumb = b'\xe9\x2d\x00\x08'  # 0x08002DE9 (thumb bit)
needle_arm   = b'\xe8\x2d\x00\x08'  # 0x08002DE8
for needle, label in ((needle_thumb, 'thumb'), (needle_arm, 'arm')):
    start = 0
    cnt = 0
    while True:
        j = orig.find(needle, start)
        if j < 0 or cnt > 40:
            break
        print(f'  {label} ptr @ file 0x{j:06X} (mem 0x{0x08000000+j:08X})')
        cnt += 1
        start = j + 1
    print(f'  [{label}] total shown: {cnt}')

# 检查成品 ROM 里是否有 0x04002DE8 / 0x04002DE9 字面量
print("\n=== 成品 ROM 中搜索 0x04002DE8/0x04002DE9 ===")
for needle, label in ((b'\xe9\x2d\x00\x04', '0x04002DE9'), (b'\xe8\x2d\x00\x04', '0x04002DE8')):
    hits = []
    start = 0
    while True:
        j = trans.find(needle, start)
        if j < 0:
            break
        hits.append(j)
        start = j + 1
    print(f'  {label}: {len(hits)} hits', [f'0x{h:06X}' for h in hits[:20]])
