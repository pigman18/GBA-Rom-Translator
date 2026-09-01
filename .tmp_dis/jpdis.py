import sys, subprocess
ROM="roms/origin/POKEMON_RUBY_AXVJ00.gba"
addr=int(sys.argv[1],16)
length=int(sys.argv[2],16)
data=open(ROM,'rb').read()
off=addr-0x08000000
raw=data[off:off+length]
tmp=".tmp_dis/jp_dump.bin"
open(tmp,'wb').write(raw)
objdump=r"C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-objdump.exe"
subprocess.run([objdump,"-D","-b","binary","-m","arm","-M","force-thumb","--start-address=0","--stop-address=%d"%length,tmp])
