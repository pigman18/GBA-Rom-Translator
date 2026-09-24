set confirm off
set pagination off
set height 0
set print elements 0
target remote 127.0.0.1:2345
printf "connected\n"
set $irq = *(unsigned int *)0x03007FFC
printf "IRQ handler = 0x%08x\n", $irq
printf "KEYINPUT before = 0x%04x\n", *(unsigned short *)0x04000130

# 先确认能写 KEYINPUT
set {unsigned short}0x04000130 = 0xFFFE
printf "KEYINPUT after write 0xFFFE = 0x%04x\n", *(unsigned short *)0x04000130
set {unsigned short}0x04000130 = 0x3FFF
printf "KEYINPUT after write 0x3FFF = 0x%04x\n", *(unsigned short *)0x04000130

# 用 IRQ 断点做帧步进
break *$irq
delete $bpnum
break *$irq
printf "breakpoint set at IRQ\n"
ignore 1 120
continue
printf "after 120 frames PC=0x%08x\n", $pc

# 按 A
set {unsigned short}0x04000130 = 0xFFFE
ignore 1 8
continue
set {unsigned short}0x04000130 = 0x3FFF
printf "A pressed+released\n"

ignore 1 60
continue
printf "after 60 more PC=0x%08x\n", $pc

# 再按一次 A
set {unsigned short}0x04000130 = 0xFFFE
ignore 1 8
continue
set {unsigned short}0x04000130 = 0x3FFF

ignore 1 180
continue
printf "after 180 more PC=0x%08x\n", $pc

dump binary memory .tmp/gdb_vram.bin 0x06000000 0x06018000
dump binary memory .tmp/gdb_pal.bin 0x05000000 0x05000400
dump binary memory .tmp/gdb_oam.bin 0x07000000 0x07000400
dump binary memory .tmp/gdb_io.bin 0x04000000 0x04000060
dump binary memory .tmp/gdb_ewram.bin 0x02000000 0x02040000
printf "dumped\n"
quit
