# 决定性 dump：粉框在屏时连 gdb，停机抓 VRAM + win + tilemap + EWRAM 分配器状态
set pagination off
set confirm off
set height 0
target remote localhost:2345

# 停机
interrupt
sleep 1

# 1) win 结构（TextPrinter）与模板 —— 0x0202E658 及其 template 指针
printf "== WIN 0x0202E658 ==\n"
x/48xb 0x0202E658
printf "== template ptr @win+0 ==\n"
set $tpl = *(unsigned int *)0x0202E658
printf "tpl=%08x\n", $tpl
x/24xb $tpl

# 2) tilemap 指针（模板+0x10 word）与 screenBase（模板+2）
set $tm = *(unsigned int *)($tpl + 0x10)
set $sb = *(unsigned char *)($tpl + 2)
printf "tilemap=%08x screenBase=%d\n", $tm, $sb
printf "== tilemap 头 512B ==\n"
x/512xb $tm
dump binary memory work/_dump_tilemap.bin $tm ($tm + 0x1000)

# 3) VRAM 全量（含所有 charBase 块）
dump binary memory work/_dump_vram.bin 0x06000000 0x06010000

# 4) EWRAM 分配器状态：位图 FEC0(0x80B)、last_tile FF48、ours 段 FF80
dump binary memory work/_dump_ewram.bin 0x0203FEC0 0x0203FFD0
printf "== last_tile=%04x cursor=%04x ==\n", *(unsigned short *)0x0203FF48, *(unsigned short *)0x0203FF40

# 5) 模板 0x081BB7E4 本体（ROM）
printf "== tpl 0x081BB7E4 ==\n"
x/24xb 0x081BB7E4

detach
quit
