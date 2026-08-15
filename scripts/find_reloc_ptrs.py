import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# relocate 指针重定向：原值指向 0x0837xxxx，被改成 0x092xxxxx
# 扫描整个 ROM，找这种指针改变
print("=== 被 relocate 重定向的指针（原 0x0837xxxx -> 新 0x09xxxxxx）===")
cnt = 0
for i in range(0, 0x08000000, 4):  # 只扫原版 8MB 范围
    o = struct.unpack_from('<I', orig, i)[0]
    t = struct.unpack_from('<I', trans, i)[0]
    if o != t:
        # 判断是否指针重定向（原指向 0x08xxxxxx 数据，新指向 0x09xxxxxx）
        if (0x08000000 <= o < 0x09000000) and (0x09000000 <= t < 0x0A000000):
            # 判断原指针是否落在图鉴说明范围 0x0837DB9C-0x08384703
            in_dex = (0x0837DB9C <= o <= 0x08384703)
            addr = 0x08000000 + i
            print(f"  指针位置 0x{addr:08X}: 0x{o:08X} -> 0x{t:08X} {'[图鉴范围内!]' if in_dex else ''}")
            cnt += 1
            if cnt > 80:
                print("  ...(截断)")
                break
print(f"\n共 {cnt} 个 relocate 指针重定向（截断前）")
