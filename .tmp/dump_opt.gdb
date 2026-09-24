set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 8
target remote 127.0.0.1:2345
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_opt_ewram.bin 0x02000000 0x02040000
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_opt_vram.bin 0x06000000 0x06018000
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_opt_iwram.bin 0x03000000 0x03008000
printf "IO DISPCNT "
x/1xh 0x04000000
printf "IO BG0CNT "
x/1xh 0x04000008
printf "IO BG1CNT "
x/1xh 0x0400000A
printf "IO BG2CNT "
x/1xh 0x0400000C
printf "IO BG3CNT "
x/1xh 0x0400000E
printf "DUMP_DONE\n"
