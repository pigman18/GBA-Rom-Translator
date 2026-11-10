# 最小连接测试 + BG0CNT watchpoint
import gdb
import sys

def log(m):
    sys.stdout.write(m + "\n")
    sys.stdout.flush()

log("[TEST] connecting...")
try:
    gdb.execute("set pagination off")
    gdb.execute("set confirm off")
    gdb.execute("target remote localhost:2345")
    log("[OK] connected")
except Exception as e:
    log("[ERR] connect: %r" % e)
    raise SystemExit

# 尝试设置 watchpoint
try:
    gdb.execute("watch *(volatile uint16_t*)0x04000008")
    log("[OK] watch set on BG0CNT")
except Exception as e:
    log("[ERR] watch: %r" % e)

log("[TEST] bp list:")
gdb.execute("info breakpoints")

# 继续运行，等待 watchpoint 触发
log("[TEST] continue...")
gdb.execute("continue")
