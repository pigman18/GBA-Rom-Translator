#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_menu_residue.py — 菜单文字「残留」一锤定音追踪。

问题：初始宠选择页（及通用菜单）左右移动时光标/文本切换，上一个名字的
「右半碎字」残留在旧位置。

假设两条：
  A) CHS 12px 字 pass1 spill 列（右4px 跨 tile）在行末/标签末未 map 到 tilemap，
     切换标签时旧 tilemap 条目残留旧字模；
  B) Mode2 字模 tile 号 = y*30+x 的行 stride 与窗口实际 width 不符（非30时错位）。

本脚本断在 CHS 写 tilemap 的 UpdateTilemap@0x080036DC，dump 每次写入的
  win 字段（CURSOR_X/Y/TILE_X/Y、TILE_BASE/TILE_OFFSET）+ abs_u/abs_l(字模 tile 号)
  + 实际 tilemap 写入地址/值。

同时断在擦除函数 FillWindowRect@0x0800413C，dump erase 范围。

判定：左右移动后，对比「新 label map 的 tilemap 列集合」是否覆盖「旧 label
map 的 tilemap 列集合」。残留 = 有 tilemap 列只被旧 label 写过、既没被 erase
覆盖也没被新 label 覆盖。

用法：
  mGBA 打开 ROM，Tools → Start GDB stub（2345），Pause。
  python gdb/trace_menu_residue.py
  然后到初始宠页左右移动；脚本记录，Ctrl-C 结束，分析 gdb/menu_residue.log。
"""
import sys, os, time, signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.gdb_patcher import GdbClient, GdbError

HOST, PORT = "127.0.0.1", 2345
LOGDIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(LOGDIR, "menu_residue.log")

# CHS 写 tilemap：UpdateTilemap(win, upper, lower)
BP_UPDATETILEMAP = 0x080036DC
# erase 核心循环：FillRect(win, entry, left, top, right, bottom)
#   反汇编 0x080040B8: r1=tilemapEntry r2=left r3=top, 栈[+0x14]=right [+0x18]=bottom
BP_FILLRECT = 0x080040B8

def u16(b, o):
    return b[o] | (b[o+1] << 8)

def u32(b, o):
    return b[o] | (b[o+1] << 8) | (b[o+2] << 16) | (b[o+3] << 24)

def log(msg):
    with open(LOG, "a", encoding="utf-8", errors="replace") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def dump_win(gdb, win):
    """dump TextPrinter 关键字段。"""
    try:
        b = gdb.read_mem(win, 0x20)
    except GdbError as e:
        log(f"    读 win 失败: {e}")
        return
    if len(b) < 0x1E:
        log(f"    win 字段不足 ({len(b)}B)")
        return
    tile_base = u16(b, 0x16)
    tile_off  = u16(b, 0x18)
    cur_x  = b[0x1A]; cur_tx = b[0x1B]
    cur_y  = b[0x1C]; cur_ty = b[0x1D]
    text_ptr = u32(b, 0x10)
    # tilemap 基址（template[0x10]，需读 template）
    tpl = u32(b, 0x00)
    tmap = 0
    if tpl:
        try:
            tb = gdb.read_mem(tpl + 0x10, 4)
            tmap = u32(tb, 0)
        except GdbError:
            pass
    log(f"    win=0x{win:08X} TILE_BASE=0x{tile_base:04X} TILE_OFF=0x{tile_off:04X} "
        f"curX={cur_x} curTX={cur_tx} curY={cur_y} curTY={cur_ty} "
        f"textPtr=0x{text_ptr:08X} tilemap=0x{tmap:08X}")

def main():
    log(f"\n===== 菜单残留追踪 @ {time.strftime('%H:%M:%S')} =====")

    gdb = GdbClient(HOST, PORT, timeout=5.0)
    for attempt in range(200):
        try:
            gdb.close(); gdb.connect(); break
        except GdbError:
            gdb.close(); time.sleep(0.5)
    else:
        print("无法连接 mGBA GDB stub（先 mGBA 开 ROM + Start GDB stub + Pause）")
        return 2

    # 先断在 UpdateTilemap 和 FillWindowRect
    for name, addr in [("UpdateTilemap", BP_UPDATETILEMAP),
                       ("FillWindowRect", BP_FILLRECT)]:
        try:
            gdb.set_sw_break(addr)
            log(f"  断点 {name} @0x{addr:08X} OK")
        except GdbError as e:
            log(f"  断点 {name} 失败: {e}")

    log("运行中：到菜单左右移动触发残留。Ctrl-C 结束。")
    n = 0
    try:
        while True:
            try:
                why = gdb.cont(timeout=600)
            except GdbError as e:
                log(f"\n[停止] {e}")
                break
            regs = gdb.read_regs()
            pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
            n += 1

            if pc == BP_UPDATETILEMAP:
                win = regs.get("r0", 0)
                abs_u = regs.get("r1", 0) & 0xFFFF
                abs_l = regs.get("r2", 0) & 0xFFFF
                log(f"\n[{n}] UpdateTilemap(CHS)  abs_u=0x{abs_u:04X} abs_l=0x{abs_l:04X}")
                dump_win(gdb, win)
            elif pc == BP_FILLRECT:
                win = regs.get("r0", 0)
                sp = regs.get("r13", 0)
                lr = regs.get("r14", 0) & ~1
                try:
                    stk = gdb.read_mem(sp, 64)
                except GdbError:
                    stk = b'\x00' * 64
                log(f"\n[{n}] FillRect(erase) r0=0x{win:08X} LR=0x{lr:08X} "
                    f"r1=0x{regs.get('r1',0)&0xFFFF:04X} "
                    f"r2={regs.get('r2',0)&0xFF} r3={regs.get('r3',0)&0xFF} "
                    f"sp=0x{sp:08X}")
                log(f"    stk[0:64]={stk.hex(' ')}")
                dump_win(gdb, win)
            else:
                log(f"\n[{n}] 意外 PC=0x{pc:08X}")
    except KeyboardInterrupt:
        log("\n[用户中断]")

    gdb.close()
    log(f"追踪结束，共 {n} 次。结果在 {LOG}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
