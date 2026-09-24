set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 5
target remote 127.0.0.1:2345
set $cnt = 0
break *0x08800084
commands
silent
set $cnt = $cnt + 1
printf "SMP win=0x%x tb=%d r2=%d r3=%d\n", $r0, $r1, $r2, $r3
if $cnt < 250
continue
end
end
continue
printf "SMP_TOTAL=%d\n", $cnt
