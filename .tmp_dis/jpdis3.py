import sys, subprocess
ROM="roms/origin/POKEMON_RUBY_AXVJ00.gba"
base=int(sys.argv[1],16); length=int(sys.argv[2],16)
data=open(ROM,'rb').read()
off=base-0x08000000
raw=data[off:off+length]
open(".tmp_dis/jp_dump.bin",'wb').write(raw)
objdump=r"C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-objdump.exe"
subprocess.run([objdump,"-D","-b","binary","-m","arm","-M","force-thumb",
    "--adjust-vma=0x%x"%base,"--start-address=%d"%base,"--stop-address=%d"%(base+length),
    ".tmp_dis/jp_dump.bin"])
