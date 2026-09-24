set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 8
target remote 127.0.0.1:2345
printf "SETUP pool before = "
x/1xw 0x08000468
set {unsigned int}0x08000468 = 0x08900000
set {unsigned short}0x08900000 = 0x3FF
printf "SETUP pool after  = "
x/1xw 0x08000468
printf "SETUP keys        = "
x/1xh 0x08900000
continue
