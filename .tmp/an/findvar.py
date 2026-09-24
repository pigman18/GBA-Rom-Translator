import struct, capstone
ROM=r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba"
d=open(ROM,'rb').read(); BASE=0x08000000
target=0x0202E6EE
lits=[BASE+i for i in range(0,len(d)-4,4) if struct.unpack_from('<I',d,i)[0]==target]
print(f"含 0x{target:08X} 的字面量位置:", [f"0x{x:08X}" for x in lits])
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
for L in lits:
    st=L-0x30
    print(f"--- 0x{st:08X} .. 0x{L:08X}")
    for ins in md.disasm(d[st-BASE:L-BASE], st):
        print(f"      {ins.address:08X}  {ins.mnemonic:8s} {ins.op_str}")
