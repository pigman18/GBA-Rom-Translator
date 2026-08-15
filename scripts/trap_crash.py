#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trap_crash.py — 抓"选招式黑屏"崩溃现场。

思路：不依赖游戏当前暂停态，直接连 mGBA GDB stub，无条件在
CallViaR0..R3（bx rN 跳转点）+ SoftReset 下断，然后 continue。
用户重置 ROM 重新触发崩溃，bx 坏指针时会命中 CallVia 断点停住，
脚本立即 dump PC/LR/SP + 全部寄存器 + CallVia 目标 + RAM 扫坏值。

用法：python scripts/trap_crash.py 0x04002DEA
"""
import socket, struct, sys, time, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.gdb_patcher import GdbClient, GdbError, CALLVIA_BPS, SOFTRESET_BP, REG_NAMES
from util.gdb_patcher import scan_ram_slots, report, parse_u32, parse_gdb_hostport, dump_animcmd_context

HOST, PORT = "127.0.0.1", 2345


def dump_all_regs(gdb):
    raw = gdb.cmd("g")
    if raw.startswith("E") or not raw:
        print("读寄存器失败", raw)
        return
    out = {}
    for i, name in enumerate(REG_NAMES):
        chunk = raw[i*8:i*8+8]
        if len(chunk) < 8:
            break
        out[name] = int.from_bytes(bytes.fromhex(chunk), "little")
    for name in REG_NAMES:
        v = out.get(name)
        if v is not None:
            tag = ""
            if name == "r15":
                tag = "  <-- PC"
            elif name == "r14":
                tag = "  <-- LR"
            elif name == "r13":
                tag = "  <-- SP"
            print(f"  {name:5s} = 0x{v:08X}{tag}")
    return out


def main():
    value = 0x04002DEA
    if len(sys.argv) > 1:
        value = parse_u32(sys.argv[1])
    print(f"trap 目标坏值 0x{value:08X}", flush=True)

    # mGBA stub 只在游戏 Pause 时响应。循环重试连接，直到成功。
    gdb = GdbClient(HOST, PORT, timeout=3.0)
    connected = False
    for attempt in range(200):
        try:
            gdb.close()
            gdb.connect()
            connected = True
            break
        except GdbError as e:
            gdb.close()
            print(f"  连接重试 {attempt+1}/200 ... ({e.__class__.__name__})", flush=True)
            time.sleep(0.5)
    if not connected:
        print("80 秒内未连上。请确认 mGBA 已 Pause（游戏暂停 = 黑屏或菜单暂停）。")
        return 2

    print(f"已连接，停因={gdb.cmd('?')}", flush=True)

    # 无条件设断点
    addrs = [SOFTRESET_BP] + [a for _, a, _ in CALLVIA_BPS]
    for name, addr, reg in CALLVIA_BPS:
        try:
            gdb.set_sw_break(addr)
            print(f"  断点 {name} 0x{addr:08X} (bx {reg})")
        except GdbError as e:
            print(f"  设断点失败 {name}: {e}")
    try:
        gdb.set_sw_break(SOFTRESET_BP)
        print(f"  断点 SoftReset 0x{SOFTRESET_BP:08X}")
    except GdbError as e:
        print(f"  设 SoftReset 断点失败: {e}")

    print("断点已设。现在 continue，请在 mGBA 里重置/重新触发崩溃...", flush=True)

    # 循环 continue：命中 CallVia 后检查目标，正常则继续跑，坏值才 dump。
    hits_normal = 0
    regs = {}
    why = ""
    while True:
        try:
            why = gdb.cont(timeout=600)
        except GdbError as e:
            print(f"等待超时/失败: {e}")
            return 1

        regs = dump_all_regs(gdb)
        pc = regs.get("r15", 0) & ~1
        lr = regs.get("r14", 0) & ~1
        sp = regs.get("r13", 0)

        # 命中 SoftReset？
        if pc == (SOFTRESET_BP & ~1):
            print(">>> 命中 SoftReset（即将重启），dump 现场...")
            break

        # 命中哪个 CallVia？
        hit_callvia = None
        for name, addr, reg in CALLVIA_BPS:
            if pc == (addr & ~1):
                hit_callvia = (name, reg, regs.get(reg, 0) & 0xFFFFFFFF)
                break

        if hit_callvia is None:
            # 未知断点，dump 现场
            print(f">>> 未知停机 PC=0x{regs.get('r15',0):08X}，dump 现场...")
            break

        name, reg, tgt = hit_callvia
        # 判断目标是否坏值（非合法代码段 + 不是 0）
        hi = (tgt >> 24) & 0xFF
        is_bad = (hi not in (0x02, 0x03, 0x08, 0x09)) and (tgt > 0x1000)
        if is_bad:
            print(f">>> 命中 CallVia{reg[-1]} (bx {reg})，坏目标 = 0x{tgt:08X}，dump 现场！")
            break
        else:
            hits_normal += 1
            if hits_normal <= 10 or hits_normal % 100 == 0:
                print(f"  忽略正常 CallVia{reg[-1]} (bx {reg}) -> 0x{tgt:08X} [{hits_normal}]", flush=True)

    print(f"\n===== 崩溃现场（停因={why}）=====")
    print(f"PC=0x{regs.get('r15',0):08X}  LR=0x{regs.get('r14',0):08X}  SP=0x{sp:08X}")

    # 判断命中哪个断点
    for name, addr, reg in CALLVIA_BPS:
        if pc == (addr & ~1):
            tgt = regs.get(reg, 0)
            print(f">>> 命中 CallVia{reg[-1]} (bx {reg})，目标 = 0x{tgt:08X}")
    if pc == (SOFTRESET_BP & ~1):
        print(">>> 命中 SoftReset（即将重启）")

    # LR 附近反汇编提示（读 LR 和 PC 附近 16 字节十六进制）
    for label, a in (("PC", regs.get("r15", 0) & ~1), ("LR", lr)):
        try:
            mem = gdb.read_mem(a, 32)
            print(f"[{label}] @0x{a:08X}: {mem.hex(' ')}")
        except GdbError as e:
            print(f"[{label}] @0x{a:08X} 读失败: {e}")

    # RAM 扫坏值
    slots = scan_ram_slots(gdb, value, limit=32)
    if slots:
        print("RAM 坏值槽:", ", ".join(f"0x{a:08X}[{b}]" for b, a in slots))

    # 也扫 CallVia 目标寄存器值
    regs_dict = regs
    print("\n所有寄存器（十六进制）:")
    for name in REG_NAMES:
        v = regs_dict.get(name)
        if v is not None:
            print(f"  {name:5s} = 0x{v:08X}")

    # AnimCmd 上下文
    dump_animcmd_context(gdb, regs)

    gdb.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
