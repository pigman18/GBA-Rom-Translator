set confirm off
set pagination off
set height 0
target remote 127.0.0.1:2345
printf "connected PC=0x%08x\n", $pc
printf "IRQ=0x%08x KEYINPUT=0x%04x\n", *(unsigned int *)0x03007FFC, *(unsigned short *)0x04000130
dump binary memory .tmp/gdb_vram.bin 0x06000000 0x06018000
dump binary memory .tmp/gdb_pal.bin 0x05000000 0x05000400
dump binary memory .tmp/gdb_oam.bin 0x07000000 0x07000400
dump binary memory .tmp/gdb_io.bin 0x04000000 0x04000060
dump binary memory .tmp/gdb_ewram.bin 0x02000000 0x02040000
printf "dumped\n"
quit
