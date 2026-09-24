set confirm off
set pagination off
target remote 127.0.0.1:2345
set {unsigned int}0x08000468 = 0x08900000
printf "PROBE="
x/1xw 0x08000468
