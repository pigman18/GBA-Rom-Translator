set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 8
target remote 127.0.0.1:2345
printf "PC=0x%08x\n", $pc

printf "\n=== 1) read original pool word @0x08000468 ===\n"
x/1xw 0x08000468

printf "\n=== 2) try ROM write: pool word -> 0x0203FFF0 ===\n"
set {unsigned int}0x08000468 = 0x0203FFF0
x/1xw 0x08000468

printf "\n=== 3) try RAM write @0x0203FFF0 = 0x3F7 ===\n"
set {unsigned short}0x0203FFF0 = 0x3F7
x/1xh 0x0203FFF0

printf "\n=== 4) try register write r1 = 0x1234 ===\n"
set $r1 = 0x1234
info registers r1

printf "\n=== 5) read gMain @0x030016E0+0x28..0x34 ===\n"
x/8xh 0x030016E0

printf "\ndone\n"
