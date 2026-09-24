set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 12
target remote 127.0.0.1:2345
printf "==== STATIC ====\n"
printf "tpl 0x081BB874 (12 words):\n"
x/12wx 0x081BB874
printf "==== DYNAMIC ====\n"
set $c = 0
break *0x08002C68
commands
silent
set $c = $c + 1
printf "ITP %d win=0x%x tb=%d a4=%d a5=%d lr=0x%x\n", $c, $r0, $r2, $r3, *(unsigned int*)$sp, $lr
x/40hx $r0
if $c >= 8
detach
quit
end
continue
end
continue
