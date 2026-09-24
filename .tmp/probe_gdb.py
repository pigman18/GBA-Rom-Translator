#!/usr/bin/env python3
"""探测 mGBA GDB stub 的 cont() 语义 + M 包写入（只连一次，采集完自动关）。"""
import os
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 2345

print(f"--- 尝试连接 127.0.0.1:{PORT} ---", flush=True)
g = GdbClient("127.0.0.1", PORT, timeout=8.0)
try:
    g.connect()
except Exception as e:
    print("连接失败:", type(e).__name__, e, flush=True)
    raise SystemExit(1)

print("连接 OK", flush=True)

try:
    regs = g.read_regs()
    print("halt regs: pc=0x%08X sp=0x%08X lr=0x%08X" % (
        regs.get("r15", 0), regs.get("r13", 0), regs.get("r14", 0)), flush=True)
except Exception as e:
    print("read_regs 失败:", type(e).__name__, e, flush=True)

try:
    r = g.cmd("M4000130,2,ff03")
    print("M 写返回:", repr(r), flush=True)
    print("读回 KEYINPUT:", g.read_mem(0x04000130, 2).hex(), flush=True)
except Exception as e:
    print("M 写失败:", type(e).__name__, e, flush=True)

t0 = time.time()
try:
    r = g.cont(timeout=1.0)
    print(f"cont 返回 ({time.time()-t0:.2f}s): {r[:150]!r}", flush=True)
except Exception as e:
    print(f"cont 异常 ({time.time()-t0:.2f}s): {type(e).__name__} {e}", flush=True)

try:
    regs = g.read_regs()
    print("cont 后 pc=0x%08X" % (regs.get("r15", 0),), flush=True)
except Exception as e:
    print("cont 后 read_regs 失败:", type(e).__name__, e, flush=True)

for i in range(2):
    try:
        g.cont(timeout=1.5)
    except Exception:
        pass
    try:
        regs = g.read_regs()
        print(f"  round{i}: pc=0x{regs.get('r15',0):08X}", flush=True)
    except Exception as e:
        print(f"  round{i}: read err {e}", flush=True)

g.close()
print("--- 探测结束 ---", flush=True)
