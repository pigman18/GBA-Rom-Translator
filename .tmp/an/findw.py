import struct, capstone, sys
ROM=r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba"
d=open(ROM,'rb').read(); BASE=0x08000000
target=int(sys.argv[1],16)
print(f"搜索对 0x{target:08X} 的引用（字面量池）")
# 收集所有字面量池里含 target 的位置
lits=[]
for i in range(0,len(d)-4,4):
    if struct.unpack_from('<I',d,i)[0]==target:
        lits.append(BASE+i)
print("  字面量出现处:", [f"0x{x:08X}" for x in lits[:20]])
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
for L in lits[:20]:
    st=L-0x40
    print(f"--- 附近代码 0x{st:08X}..0x{L:08X}")
    for ins in md.disasm(d[st-BASE:L-BASE], st):
        print(f"      {ins.address:08X}  {ins.mnemonic:8s} {ins.op_str}")
