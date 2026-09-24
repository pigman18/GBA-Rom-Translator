set confirm off
set pagination off
set height 0
set width 0
set $f = 0
target remote 127.0.0.1:2345
printf "connected pc=0x%08x\n", $pc
break *0x08000432
commands
silent
set $f = $f + 1
if $f > 240
  printf "DRIVE_DONE frames=%d\n", $f
  detach
  quit
end
if $f % 60 == 0
  printf "frame %d\n", $f
end
set $r1 = 1023
continue
end
continue
