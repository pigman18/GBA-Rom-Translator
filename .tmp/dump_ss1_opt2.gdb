set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 8
target remote 127.0.0.1:2345
dump binary memory C:\code\GBA-Rom-Translator\.tmp\drive_ss1_opt2_ewram.bin 0x02000000 0x02040000
printf "DUMP_DONE\n"
