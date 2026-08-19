#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
step_trace.py — 单步追踪，抓"选定招式后崩溃"的最后指令轨迹。

原理：
- 连 mGBA GDB stub
- 你操作游戏到"招式列表已打开、即将选定招式"
- 脚本循环单步（stepi），记录每条 PC 到 trace.log
- 崩溃（软复位/连接断开）时，trace.log 末尾就是崩溃前最后执行的指令序列

用法：
  python scripts/step_trace.py
配合：mGBA 打开 ROM + Start GDB stub + Pause 在招式列表前。
"""
import sys, os, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.debug_patcher import GdbClient, GdbError, REG_NAMES

HOST, PORT = "127.0.0.1", 2345
TRACE_FILE = os.path.join(os.path.dirname(__file__), "trace.log")

def read_pc(gdb):
    raw = gdb.cmd("g")
    if raw.startswith("E") or not raw:
        return None
    # r15 是第 16 个寄存器
    chunk = raw[15*8:15*8+8]
    if len(chunk) < 8:
        return None
    return int.from_bytes(bytes.fromhex(chunk), "little")

def read_full_regs(gdb):
    raw = gdb.cmd("g")
    out = {}
    for i, name in enumerate(REG_NAMES):
        chunk = raw[i*8:i*8+8]
        if len(chunk) >= 8:
            out[name] = int.from_bytes(bytes.fromhex(chunk), "little")
    return out

def main():
    gdb = GdbClient(HOST, PORT, timeout=3.0)
    connected = False
    for attempt in range(200):
        try:
            gdb.close()
            gdb.connect()
            connected = True
            break
        except GdbError:
            gdb.close()
            print(f"  重试连接 {attempt+1}/200...")
            time.sleep(0.5)
    if not connected:
        print("无法连接。请确认 mGBA 已 Start GDB stub 且游戏 Pause。")
        return 2

    print(f"已连接，停因={gdb.cmd('?')}")
    print("现在游戏应暂停在招式列表（尚未选定招式）。")
    print("请在 5 秒内准备好，脚本将开始单步...")
    time.sleep(5)

    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n===== 新追踪 @ {time.strftime('%H:%M:%S')} =====\n")

    step = 0
    while step < 100000:
        try:
            pc = read_pc(gdb)
            if pc is None:
                break
            with open(TRACE_FILE, "a", encoding="utf-8") as f:
                f.write(f"{step:6d}  PC=0x{pc:08X}  LR=0x{...}\n")
        except Exception:
            pass

        # 单步
        try:
            r = gdb.cmd("s")
            step += 1
            if step % 1000 == 0:
                print(f"  已单步 {step} 次...", flush=True)
        except GdbError as e:
            print(f"\n[停止] 单步失败/连接断开: {e}")
            print(f"已记录 {step} 步到 {TRACE_FILE}")
            break

    # 尝试读最终寄存器
    try:
        regs = read_full_regs(gdb)
        print("\n最终寄存器:")
        for name in REG_NAMES:
            if name in regs:
                tag = "  <-- PC" if name == "r15" else ("  <-- LR" if name == "r14" else "")
                print(f"  {name:5s} = 0x{regs[name]:08X}{tag}")
    except Exception as e:
        print(f"读最终寄存器失败: {e}")

    gdb.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
