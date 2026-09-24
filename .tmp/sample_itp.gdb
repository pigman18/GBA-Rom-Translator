set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 12
target remote 127.0.0.1:2345
set $c = 0
break *0x08002C68
commands
silent
set $c = $c + 1
set $tpl = *(unsigned int*)$r0
printf "ITP %d win=0x%x tb=%d a4=%d a5=%d lr=0x%x tpl=0x%x tiled=0x%x tmap=0x%x\n", $c, $r0, $r2, $r3, *(unsigned int*)$sp, $lr, $tpl, *(unsigned int*)($tpl+12), *(unsigned int*)($tpl+16)
if $c < 120
continue
end
end
set {unsigned short}0x08900000 = 0x3FE
continue
