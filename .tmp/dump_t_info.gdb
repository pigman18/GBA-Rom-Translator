set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 8
target remote 127.0.0.1:2345
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_t_info_ewram.bin 0x02000000 0x02040000
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_t_info_vram.bin 0x06000000 0x06018000
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_t_info_iwram.bin 0x03000000 0x03008000
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_t_info_pal.bin 0x05000000 0x05000400
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_t_info_io.bin 0x04000000 0x04000060
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
printf "IO BG0HOFS "
x/1xh 0x04000010
printf "IO BG0VOFS "
x/1xh 0x04000012
printf "IO BG1HOFS "
x/1xh 0x04000014
printf "IO BG1VOFS "
x/1xh 0x04000016
printf "IO BG2HOFS "
x/1xh 0x04000018
printf "IO BG2VOFS "
x/1xh 0x0400001A
printf "IO BG3HOFS "
x/1xh 0x0400001C
printf "IO BG3VOFS "
x/1xh 0x0400001E
printf "DUMP_DONE\n"
