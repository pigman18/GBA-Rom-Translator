import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
no_poke = open('roms/outputs/POKEMON_RUBY_AXVJ00_nopoke.gba','rb').read()  # 不含图鉴说明
with_poke = open('roms/outputs2/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()  # 含图鉴说明

# 找"含图鉴说明后，相比原版改动了，但不含图鉴说明时保持原版"的地址
# 即：图鉴说明【独有】改动的地址（不含图鉴说明时这些地址 == 原版，含图鉴说明后 != 原版）
exclusive = []
n = min(len(orig), len(no_poke), len(with_poke))
for i in range(0, n, 4):
    o = struct.unpack_from('<I', orig, i)[0]
    a = struct.unpack_from('<I', no_poke, i)[0]
    b = struct.unpack_from('<I', with_poke, i)[0]
    # 不含图鉴说明时 == 原版（没动），含图鉴说明后 != 原版（动了）
    if a == o and b != o:
        exclusive.append(0x08000000 + i)

print(f"图鉴说明【独有】改动 {len(exclusive)} 处（不含图鉴说明时这些保持原版）:")

# 重点看代码区 0x0800xxxx（动画/战斗代码）
code_ex = [a for a in exclusive if 0x08000000 <= a <= 0x08100000]
print(f"\n其中代码区 0x0800xxxx-0x0810xxxx 共 {len(code_ex)} 处:")
for a in code_ex[:80]:
    off = a - 0x08000000
    print(f"  0x{a:08X}: 原版=0x{struct.unpack_from('<I',orig,off)[0]:08X} -> 有图鉴=0x{struct.unpack_from('<I',with_poke,off)[0]:08X}")
