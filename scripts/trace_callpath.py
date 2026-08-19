#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_callpath.py — 记录战斗消息打印路径的调用轨迹。

在 StringExpandPlaceholders / RunTextPrinter 入口下硬件断点，
命中即记录 PC/LR/SP 后 continue。崩溃（连接断开）时，日志末尾
即崩溃前的调用链。

用法: python scripts/trace_callpath.py
前提: mGBA 打开 ROM + Start GDB stub + 已 Pause 在战斗前任意点。
"""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.debug_patcher import GdbClient, GdbError, REG_NAMES

HOST, PORT = "127.0.0.1", 2345
LOG = os.path.join(os.path.dirname(__file__), "callpath.log")

# 战斗消息打印关键入口（日版）
BPS = [
    ("StringExpandPlaceholders", 0x08004530),
    ("RunTextPrinter",           0x08002DE8),
    ("BattleStringExpand",       0x08004530),  # 同名
]
# 去掉重复，用 set
seen = set()
UNIQUE_BPS = []
for name, addr in BPS:
    if addr not in seen:
        seen.add(addr)
        UNIQUE_BPS.append((name, addr))

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
    connected = False
    for attempt in range(200):
        try:
            gdb.close(); gdb.connect(); connected = True; break
        except GdbError:
            gdb.close()
            print(f"  重试 {attempt+1}/200...")
            time.sleep(0.5)
    if not connected:
        print("无法连接。请确认 mGBA Start GDB stub 且 Pause。")
        return 2

    log(f"已连接，停因={gdb.cmd('?')}")

    # 设硬件断点（Z1 hwbreak kind=2 = 16bit Thumb）。ROM 是只读的，
    # 软断点 Z0 无法写入断点指令，必须用硬件断点才能在 ROM 代码上拦截。
    for name, addr in UNIQUE_BPS:
        try:
            r = gdb.cmd(f"Z1,{addr:x},2")
            log(f"  HW断点 {name} @ 0x{addr:08X} -> {r}")
        except GdbError as e:
            log(f"  设 HW 断点失败 {name}: {e}")

    log("开始追踪：请在游戏里操作到战斗→选定招式→触发黑屏...")
    hits = 0
    while True:
        try:
            why = gdb.cont(timeout=300)
        except GdbError as e:
            log(f"\n[连接断开] {e}")
            log(f"共记录 {hits} 次命中。检查 {LOG} 末尾。")
            break

        regs = regs_of(gdb)
        pc = regs.get("r15", 0) & ~1
        lr = regs.get("r14", 0) & ~1
        sp = regs.get("r13", 0)

        # 命中哪个断点
        name = "?"
        for n, addr in UNIQUE_BPS:
            if pc == (addr & ~1):
                name = n; break
        hits += 1
        log(f"  [{hits:4d}] {name}  PC=0x{pc:08X} LR=0x{lr:08X} SP=0x{sp:08X} r0=0x{regs.get('r0',0):08X}")

    gdb.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
