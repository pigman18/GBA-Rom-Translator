set confirm off
set pagination off
set height 0
set width 0
target remote 127.0.0.1:2345
set {unsigned int}0x08000468 = 0x08900000
set {unsigned short}0x08900000 = 0x3FF
x/1xw 0x08000468
continue
