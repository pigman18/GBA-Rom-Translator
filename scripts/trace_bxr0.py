#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_bxr0.py — 精准抓 sub_802D798 的 bx r0 返回跳转。

断点：
  - 0x0802D864  bl RunTextPrinter（记录调用）
  - 0x0802D86E  bx r0（抓 r0 值，看是否变坏）

崩溃（连接断开）时，最后一次 bx r0 的 r0 值就是坏跳转地址。
"""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.gdb_patcher import GdbClient, GdbError, REG_NAMES

HOST, PORT = "127.0.0.1", 2345
LOG = os.path.join(os.path.dirname(__file__), "bxr0.log")

BPS = [
    ("sub798_bl_RunTextPrinter", 0x0802D864),
    ("sub798_bxr0",              0x0802D86E),
]

def regs_of(gdb):
    raw = gdb.cmd("g")
    out = {}
    for i, name in enumerate(REG_NAMES):
        c = raw[i*8:i*8+8]
        if len(c) >= 8:
            out[name] = int.from_bytes(bytes.fromhex(c), "little")
    return out

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def main():
    open(LOG, "a", encoding="utf-8").write(f"\n===== 新追踪 @ {time.strftime('%H:%M:%S')} =====\n")

    gdb = GdbClient(HOST, PORT, timeout=3.0)
    for attempt in range(200):
        try:
            gdb.close(); gdb.connect(); break
        except GdbError:
            gdb.close()
            time.sleep(0.5)
    else:
        print("无法连接"); return 2

    log(f"已连接，停因={gdb.cmd('?')}")

    for name, addr in BPS:
        r = gdb.cmd(f"Z1,{addr:x},2")
        log(f"  HW断点 {name} @ 0x{addr:08X} -> {r}")

    log("开始追踪：选招式触发黑屏...")
    n = 0
    while True:
        try:
            why = gdb.cont(timeout=300)
        except GdbError as e:
            log(f"\n[连接断开] {e}. 共 {n} 次命中。")
            break

        regs = regs_of(gdb)
        pc = regs.get("r15", 0) & ~1
        n += 1
        if pc == 0x0802D86E:
            log(f"  [{n}] bx r0  PC=0x{pc:08X} r0=0x{regs.get('r0',0):08X} SP=0x{regs.get('r13',0):08X} LR=0x{regs.get('r14',0):08X}  <== bx r0 目标")
        else:
            log(f"  [{n}] bl RTP   PC=0x{pc:08X} r0=0x{regs.get('r0',0):08X} SP=0x{regs.get('r13',0):08X}")

    gdb.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
