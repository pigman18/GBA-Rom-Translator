import sys
ROM="roms/origin/POKEMON_RUBY_AXVJ00.gba"
addr=int(sys.argv[1],16); n=int(sys.argv[2])
data=open(ROM,'rb').read()
off=addr-0x08000000
# 4-byte LE entries (ARM func ptrs)
import struct
for i in range(n):
    v=struct.unpack('<I', data[off+i*4:off+i*4+4])[0]
    print(f"  [{i}] {v:08X}  (thumb=0x{v&~1:08X})")
