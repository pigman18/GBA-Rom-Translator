#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_black_block.py — 放技能黑块/黑屏 一锤定音追踪。

连接 mGBA GDB stub（127.0.0.1:2345），在战斗里放带背景动画的招式（冲浪/潜水等），
断在关键函数，dump 决定性字段：

  - GetBlankTileNum @0x080041BC：返回 r0（真正的 blank tile 号）
    同时 dump TextPrinter*（参数 r0）的 textMode[0x0A]/fontNum[0x0B]/TILE_BASE[0x16]/TILE_OFFSET[0x18]
  - Text_ClearWindow @0x08003BA8：谁在清屏 + blank tile 填充
  - UpdateTilemap   @0x080036DC：CHS hook 写 tilemap 时传的 abs_u(r1)/abs_l(r2) + win 字段

用法：
  python scripts/trace_black_block.py [--gdb 127.0.0.1:2345] [--limit 200]

判定：
  1) blank tile 到底是 0x190 还是 0x264（=0x190+0xD4，charblock1）
  2) CHS 写的 abs_u/abs_l 是否越过 0x200（charblock1/2，LoadMoveBg 区）
  3) textMode/fontNum 真实值（决定 GetBlankTileNum 走哪条分支）
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.debug_patcher import GdbClient, GdbError, REG_NAMES

HOST, PORT = "127.0.0.1", 2345
LOG = os.path.join(os.path.dirname(__file__), "black_block.log")

BPS = [
    ("GetBlankTileNum", 0x080041BC),
    ("Text_ClearWindow", 0x08003BA8),
    ("UpdateTilemap", 0x080036DC),
]

def u16(b, o):
    return b[o] | (b[o+1] << 8)

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def dump_tp(gdb, tp, indent="  "):
    """dump TextPrinter 关键字段: textMode/fontNum/TILE_BASE/TILE_OFFSET/cursor"""
    try:
        b = gdb.read_mem(tp, 0x20)
    except GdbError as e:
        log(f"{indent}读 TextPrinter 失败: {e}")
        return
    if len(b) < 0x1E:
        log(f"{indent}TextPrinter 字段不足 ({len(b)}B)")
        return
    textMode = b[0x0A]; fontNum = b[0x0B]
    tile_base = u16(b, 0x16); tile_off = u16(b, 0x18)
    cur_x = b[0x1A]; cur_tx = b[0x1B]; cur_y = b[0x1C]; cur_ty = b[0x1D]
    log(f"{indent}TextPrinter=0x{tp:08X} textMode={textMode} fontNum={fontNum} "
        f"TILE_BASE=0x{tile_base:04X} TILE_OFFSET=0x{tile_off:04X} "
        f"curX={cur_x} curTX={cur_tx} curY={cur_y} curTY={cur_ty}")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--gdb", default=f"{HOST}:{PORT}")
    ap.add_argument("--limit", type=int, default=300)
    args = ap.parse_args()

    host, port = args.gdb.rsplit(":", 1)
    port = int(port)

    open(LOG, "a", encoding="utf-8").write(f"\n===== 黑块追踪 @ {time.strftime('%H:%M:%S')} =====\n")

    gdb = GdbClient(host, port, timeout=3.0)
    for attempt in range(200):
        try:
            gdb.close(); gdb.connect(); break
        except GdbError:
            gdb.close(); time.sleep(0.5)
    else:
        print("无法连接 mGBA GDB stub"); return 2

    log(f"已连接，停因={gdb.cmd('?')}")
    for name, addr in BPS:
        try:
            gdb.set_sw_break(addr)
            log(f"  断点 {name} @ 0x{addr:08X} OK")
        except GdbError as e:
            log(f"  断点 {name} @ 0x{addr:08X} 失败: {e}")

    log("追踪中：放带背景动画招式（冲浪/怪力/潜水…）触发黑块...")
    n = 0
    while n < args.limit:
        try:
            why = gdb.cont(timeout=600)
        except GdbError as e:
            log(f"\n[停止] {e}。共 {n} 次命中。")
            break

        regs = gdb.read_regs()
        pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
        n += 1

        if pc == 0x080041BC:
            # GetBlankTileNum：参数 r0 = win，返回也 r0
            win = regs.get("r0", 0)
            log(f"\n[{n}] GetBlankTileNum 命中 r0(win)=0x{win:08X}")
            dump_tp(gdb, win)
            # 单步执行到返回，读返回值
            # 简化：设断点到 0x08004222 (pop {r1}; bx r1) 前不好单步，直接看后续
        elif pc == 0x08003BA8:
            win = regs.get("r0", 0)
            log(f"\n[{n}] Text_ClearWindow 命中 r0(win)=0x{win:08X}")
            dump_tp(gdb, win)
        elif pc == 0x080036DC:
            win = regs.get("r0", 0)
            abs_u = regs.get("r1", 0) & 0xFFFF
            abs_l = regs.get("r2", 0) & 0xFFFF
            log(f"\n[{n}] UpdateTilemap(CHS) abs_u=0x{abs_u:04X} abs_l=0x{abs_l:04X}")
            dump_tp(gdb, win)
        else:
            log(f"\n[{n}] 意外 PC=0x{pc:08X}")
            continue

    gdb.close()
    log(f"追踪结束，共 {n} 次命中。结果在 {LOG}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
