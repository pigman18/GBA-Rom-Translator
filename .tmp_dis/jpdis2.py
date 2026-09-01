import sys, subprocess, struct
ROM="roms/origin/POKEMON_RUBY_AXVJ00.gba"
base=int(sys.argv[1],16)
length=int(sys.argv[2],16)
data=open(ROM,'rb').read()
off=base-0x08000000
raw=data[off:off+length]
tmp=".tmp_dis/jp_dump.bin"
open(tmp,'wb').write(raw)
objdump=r"C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-objdump.exe"
out=subprocess.run([objdump,"-D","-b","binary","-m","arm","-M","force-thumb","--start-address=0","--stop-address=%d"%length,tmp],capture_output=True,text=True).stdout
for line in out.splitlines():
    m=line.split()
    if len(m)>=3 and m[1].endswith(':') and ('bl' in m or 'b.n' in m or 'cbz' in m):
        try:
            off16=int(m[0].rstrip(':'),16)
            # parse branch target from disassembly if present
        except: pass
    print(line)
