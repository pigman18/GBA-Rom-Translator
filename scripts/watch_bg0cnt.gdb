# Watch BG0CNT (0x04000008) 写断点测试
set pagination off
set confirm off
target remote localhost:2345
echo ===CONNECTED===\n
# 尝试在 BG0CNT 设 16-bit 硬件写断点
watch *(volatile unsigned short*)0x04000008
echo ===WATCH SET===\n
info breakpoints
continue
