set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 8
target remote 127.0.0.1:2345
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_bypOpt_ewram.bin 0x02000000 0x02040000
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_bypOpt_vram.bin 0x06000000 0x06018000
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_bypOpt_iwram.bin 0x03000000 0x03008000
printf "DUMP_DONE\n"
