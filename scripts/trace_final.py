#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_final.py — 一次抓全崩溃现场关键信息。

断点：
  - 0x0802D864  bl RunTextPrinter（每次命中记录 r0=TextPrinter* 及关键字段）
  - 0x0802D86E  bx r0（抓 r0 坏值）

对每次 RunTextPrinter 命中，dump r0 指向的 TextPrinter 结构体关键字段：
  +0x0A textMode, +0x0B fontNum, +0x10 text_ptr, +0x14 text_index,
  +0x16 TILE_BASE, +0x18 TILE_OFFSET, +0x1A CURSOR_X, +0x1C CURSOR_Y

崩溃（连接断开）时，最后一条记录就是崩溃现场。
"""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.gdb_patcher import GdbClient, GdbError, REG_NAMES

HOST, PORT = "127.0.0.1", 2345
LOG = os.path.join(os.path.dirname(__file__), "final.log")
# 过滤掉战斗血条/命令条等无关 RunTextPrinter：这些文本 mode=0，会一直刷屏。

BPS = [
    ("blRunTextPrinter", 0x0802D864),
    ("bxr0",              0x0802D86E),
]

FIELDS = [
    ("textMode", 0x0A, 1), ("fontNum", 0x0B, 1),
    ("text_ptr", 0x10, 4), ("text_index", 0x14, 2),
    ("TILE_BASE", 0x16, 2), ("TILE_OFFSET", 0x18, 2),
    ("CURSOR_X", 0x1A, 1), ("CURSOR_TILE_X", 0x1B, 1),
    ("CURSOR_Y", 0x1C, 1), ("CURSOR_TILE_Y", 0x1D, 1),
]

def regs_of(gdb):
    raw = gdb.cmd("g")
    out = {}
    for i, name in enumerate(REG_NAMES):
        c = raw[i*8:i*8+8]
        if len(c) >= 8:
            out[name] = int.from_bytes(bytes.fromhex(c), "little")
    return out

def read_mem(gdb, addr, n):
    try:
        raw = gdb.cmd(f"m{addr:x},{n:x}")
        if raw.startswith("E") or not raw:
            return None
        return bytes.fromhex(raw)
    except Exception:
        return None

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def main():
    open(LOG, "a", encoding="utf-8").write(f"\n===== 追踪 @ {time.strftime('%H:%M:%S')} =====\n")

    gdb = GdbClient(HOST, PORT, timeout=3.0)
    for attempt in range(200):
        try:
            gdb.close(); gdb.connect(); break
        except GdbError:
            gdb.close(); time.sleep(0.5)
    else:
        print("无法连接"); return 2

    log(f"已连接，停因={gdb.cmd('?')}")
    for name, addr in BPS:
        r = gdb.cmd(f"Z1,{addr:x},2")
        log(f"  HW断点 {name} @ 0x{addr:08X} -> {r}")

    log("追踪中：选招式触发黑屏...")
    n = 0
    while True:
        try:
            why = gdb.cont(timeout=300)
        except GdbError as e:
            log(f"\n[连接断开 = 崩溃] {e}. 共 {n} 次命中。")
            break

        regs = regs_of(gdb)
        pc = regs.get("r15", 0) & ~1
        r0 = regs.get("r0", 0)
        sp = regs.get("r13", 0)
        n += 1

        if pc == 0x0802D86E:
            # bx r0：抓 r0 坏值 + 栈顶
            log(f"  [{n:4d}] *** bx r0 **  r0=0x{r0:08X} (要跳去的地址) SP=0x{sp:08X}")
            stk = read_mem(gdb, sp, 16)
            if stk:
                import struct
                words = [hex(struct.unpack_from('<I', stk, i)[0]) for i in range(0,16,4)]
                log(f"        栈顶[sp..sp+16]: {' '.join(words)}")
        else:
            # bl RunTextPrinter：dump TextPrinter 字段
            tp = r0  # r0 = TextPrinter*
            fields = []
            for name, off, size in FIELDS:
                data = read_mem(gdb, tp + off, size)
                if data is None:
                    fields.append(f"{name}=?")
                    continue
                if size == 1:
                    v = data[0]; fields.append(f"{name}=0x{v:02X}")
                elif size == 2:
                    v = data[0] | (data[1] << 8); fields.append(f"{name}=0x{v:04X}")
                else:
                    v = data[0] | (data[1]<<8) | (data[2]<<16) | (data[3]<<24)
                    fields.append(f"{name}=0x{v:08X}")
            text_mode = read_mem(gdb, tp + 0x0a, 1)
            if text_mode is None or text_mode[0] == 0:
                continue
            log(f"  [{n:4d}] RTP  r0(TP)=0x{tp:08X} SP=0x{sp:08X} | {' '.join(fields)}")

    gdb.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
