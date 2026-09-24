set confirm off
set pagination off
set height 0
set width 0
set $n = 0
set $irq = 0
target remote 127.0.0.1:2345
printf "CONNECTED PC=0x%08x\n", $pc
printf "IRQVEC=0x%08x\n", *(unsigned int*)0x03007ffc

# —— 机制验证：IRQ 处理器（每帧必调）——
break *0x03001b70
commands
silent
set $irq = $irq + 1
if $irq == 1
  printf "IRQ HIT ok (mechanism works)\n"
end
continue
end

break *0x08800080
commands
silent
set $w = $r0
printf "INIT_HOOK win=0x%08x tbase_in=%u\n", $w, $r1
if $w != 0
  set $t = *(unsigned int*)$w
  printf "     tpl=0x%08x tplC=0x%08x tpl9=%u base=%u off=%u tmx=%u\n", $t, *(unsigned int*)($t+12), *(unsigned char*)($t+9), *(unsigned short*)($w+22), *(unsigned short*)($w+24), *(unsigned char*)($w+26)
end
set $n = $n + 1
continue
end

break *0x08800c58
commands
silent
printf "CANVAS_BASE_FOR win=0x%08x\n", $r0
set $n = $n + 1
continue
end

break *0x08800834
commands
silent
set $w = $r0
set $t = *(unsigned int*)$w
printf "PNC win=0x%08x tpl=0x%08x tileData=0x%08x base=%u off=%u tm=%u\n", $w, $t, *(unsigned int*)($t+12), *(unsigned short*)($w+22), *(unsigned short*)($w+24), *(unsigned char*)($w+8)
set $n = $n + 1
if $n > 50
  printf "---- limit $n ----\n"
  quit
end
continue
end

continue
