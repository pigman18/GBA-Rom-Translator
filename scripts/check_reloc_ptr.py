import struct, json
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 0x0837DB9C 起的 relocate 指针槽，看原版值 vs 成品值
print("=== 0x0837DB9C 附近 relocate 指针槽 原版vs成品 ===")
for addr in range(0x0837DB90, 0x0837DC00, 4):
    off = addr - 0x08000000
    o = struct.unpack_from('<I', orig, off)[0]
    t = struct.unpack_from('<I', trans, off)[0]
    mark = ' <== 改' if o != t else ''
    print(f"  0x{addr:08X}: orig=0x{o:08X} trans=0x{t:08X}{mark}")

# 找这些 entry 的 pointer_sources（relocate 会改哪些指针位置）
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])
print("\n=== 图鉴说明模块 relocate 条目的完整信息（含 pointer_sources）===")
cnt = 0
for e in entries:
    if e.get('module') == '图鉴说明' and e.get('type') == 'relocate':
        addr = int(str(e.get('address','0')),16)
        if 0x0837D000 <= addr <= 0x08380000:
            print(f"  addr=0x{addr:08X} id={e.get('id')} byte_len={e.get('byte_length')} phrases={e.get('phrase_code')}")
            cnt += 1
            if cnt >= 8:
                break
