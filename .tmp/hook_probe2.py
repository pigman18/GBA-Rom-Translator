#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hook_probe2 — 在 hook 内部各「分支判定点」下断点，**直接读寄存器真值**。

为什么这么设计
==============
mGBA 的 GDB stub **读写 EWRAM 都被 NAK**，而 `win` / `tpl` 大概率落在
0x02000000+ ⇒ 不能靠 `m` 读内存拿 `tileData`。
但 `InitTextPrinter_hook_C` 的机器码里 `tileData` 会被**加载进 r2**（0x88000b2），
所以只要把断点打在那条指令**之前**（0x088000B4），r2 就是门控真值本身。

反汇编依据（`hook/out/game.bin`，--adjust-vma=0x08800000，force-thumb）：
  8800080 push {r4,lr}
  8800082 movs r4,r0            ; r4 = win
  8800084 movs r0,r1            ; r0 = tile_base（默认返回值）
  8800086 cmp  r4,#0
  8800088 beq  0x88000bc        ; win==0 -> return
  880008a..9c r3 = *(u32*)win   ; tpl = win_template(win)
  880009e beq  0x88000bc        ; tpl==0  -> return
  88000a0..b2 r2 = *(u32*)(tpl+0x0C)   ; ← tileData
  88000b4 movs r1,#192 / lsls r1,#19   ; 0x06000000
  88000b8 cmp  r2,r1
  88000ba beq  0x88000c2        ; tileData == 0x06000000 -> 门控A过
  88000bc pop {r4}; pop {r1}; bx r1    ; 统一出口
  88000c2 ldrb r3,[r3,#9]       ; tm = tpl->textMode
  88000c4 cmp  r3,#1
  88000c6 bhi  0x88000bc        ; tm > 1 -> return
  88000c8 bl   0x8800bc4        ; v8_phase_reset()
  88000cc movs r0,r4
  88000ce bl   0x8800c58        ; chs_canvas_base_for(win)
  88000d2 b    0x88000bc        ; ← r0 = 画布基址
"""
import collections
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, r"C:\code\GBA-Rom-Translator\scripts")
import mgba_drive as md   # noqa: E402

STATE = (r"C:\code\GBA-Rom-Translator\roms\outputs"
         r"\POKEMON_RUBY_AXVJ00_translated.ss1")
TAG = "hookprobe2"

# 地址 -> (标签, 关注点说明)
BPS = {
    0x08800084: ("entry+4        ", "r1=tile_base(官方请求) r4=win"),
    0x0880009E: ("tpl built      ", "★r3=tpl(=*(u32*)win)"),
    0x088000A0: ("tpl!=0         ", "r3=tpl r4=win"),
    0x088000B4: ("tileData loaded", "★r2=tileData r3=tpl"),
    0x088000C4: ("gateA ok, tm   ", "r3=tpl->textMode"),
    0x088000C8: ("BOTH gates ok  ", "→ 走画布路径"),
    0x088000CE: ("call canvas    ", "bl chs_canvas_base_for"),
    0x088000D2: ("canvas returned", "★r0=画布基址"),
}

# mGBA 的硬件断点数有上限（实测 7 个全报 OK 但只有部分真生效）
# ⇒ 每次务必用 `--only` 限定到 ≤3 个，避免「没装上」被误读成「没走到」。
DEFAULT_ONLY = "0x8800084,0x880009E"


def regs(ghex: str):
    """'g' 应答 -> 寄存器列表。mGBA 返 17 个（r0-r12,sp,lr,pc,cpsr）。"""
    try:
        b = bytes.fromhex(ghex)
    except ValueError:
        return []
    return [int.from_bytes(b[i:i + 4], "little") for i in range(0, len(b) - 3, 4)]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=DEFAULT_ONLY,
                    help="逗号分隔的断点地址（≤3 个，避开 hwbreak 上限）")
    ap.add_argument("--hold", type=float, default=4.0,
                    help="导航到设置页后，停在设置页的秒数（0 = 只开菜单）")
    ap.add_argument("--trace-at", type=lambda s: int(s, 16), default=0,
                    help="首次命中该地址时做单步跟踪（十六进制，如 0x8800084）")
    ap.add_argument("--trace-n", type=int, default=24, help="单步步数")
    args = ap.parse_args()
    only = {int(x, 16) for x in args.only.split(",") if x.strip()}
    bps = {a: v for a, v in BPS.items() if a in only}
    tag = TAG + "_" + "_".join(f"{a:07x}"[-6:] for a in sorted(bps))

    md.kill_mgba()
    time.sleep(0.6)
    emu_log = open(md.TMP / f"emu_{tag}.log", "w", encoding="utf-8")
    subprocess.Popen([str(md.MGBA_EXE), "-g", "-3", "-t", STATE, str(md.ROM)],
                     cwd=str(md.MGBA_DIR), stdout=emu_log, stderr=subprocess.STDOUT)

    if not md.wait_port(30.0):
        print("stub 端口未开")
        return 1

    # ---- gdb 一次性 setup：把 ReadKeys 池字重定向到注入区 ----
    setup = md.TMP / f"setup_{TAG}.gdb"
    setup.write_text(
        "set confirm off\nset pagination off\nset height 0\nset width 0\n"
        f"target remote 127.0.0.1:{md.PORT}\n"
        f"set {{unsigned int}}0x{md.POOL_ADDR:08X} = 0x{md.KEYS_ADDR:08X}\n"
        f"set {{unsigned short}}0x{md.KEYS_ADDR:08X} = 0x{md.NO_KEY:03X}\n"
        f"x/1xw 0x{md.POOL_ADDR:08X}\n"
        "continue\n", encoding="ascii", newline="\n")
    g = subprocess.Popen([str(md.GDB_EXE), "-nx", "-batch", "-x", str(setup)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace")
    time.sleep(3.0)
    g.kill()
    out, _ = g.communicate(timeout=15)
    print("[setup]", " | ".join(x.strip() for x in (out or "").splitlines()
                                if "0x8000468" in x))
    time.sleep(1.2)

    rsp = md.RSP(timeout=8.0)
    rsp.drain(0.8)
    rsp.fire_and_forget("c")
    t0 = time.time()
    print("[probe] running")

    def key_at(t, raw):
        dt = t0 + t - time.time()
        if dt > 0:
            time.sleep(dt)
        rsp.fire_and_forget("M%x,2:%s" % (md.KEYS_ADDR, md.u16le(raw).hex()))

    K = md.KEYBITS
    def press(t, name, hold=0.62):
        key_at(t, md.NO_KEY & ~(1 << K[name]))
        key_at(t + hold, md.NO_KEY)

    # ---- EWRAM 读能力实测（一次）----
    try:
        v = rsp.peek(0x02000000, 4)
        print(f"[cap] EWRAM m 读 -> OK {v.hex()}")
    except Exception as e:                                  # noqa: BLE001
        print(f"[cap] EWRAM m 读 -> 拒 {e}")

    # ---- 阶段 1：导航到设置页（已验证时间表）----
    press(3.00, "START")
    press(5.33, "DOWN")
    press(7.67, "A")
    time.sleep(max(0.8, args.hold))

    # ---- 阶段 2：下断点 ----
    for addr in sorted(bps):
        try:
            ack = rsp.cmd("Z0,%x,2" % addr, retries=4)
            print(f"[arm] 0x{addr:08X} {bps[addr][0]} -> {ack!r}")
        except Exception as e:                              # noqa: BLE001
            print(f"[arm] 0x{addr:08X} 失败 {e}")
    rsp.fire_and_forget("c")

    # ---- 阶段 3：后台 pump 线程收命中，主线程继续喂键 ----
    hits = collections.Counter()
    samples = collections.defaultdict(list)
    dist = collections.defaultdict(collections.Counter)     # addr -> value -> n
    lock = threading.Lock()
    stop = threading.Event()
    ncap = 0
    stop_cap = 8

    raw_stops = []
    traced = {"done": False}
    trace_lines = []

    def do_trace():
        """从当前 PC 单步 N 次，记录 PC / r2 / r3。"""
        pc = -1
        trace_lines.append("  step  PC          r2(tileData) r3(tpl)     r0")
        for i in range(args.trace_n):
            try:
                rsp.send("s")
                # 单步后可能先来 ACK。用 token 循环拿到停止包。
                for _ in range(8):
                    kind, val = rsp.token()
                    if kind == "pkt" and val[:1] in (b"S", b"T"):
                        break
                gh = rsp.cmd("g")
                rs = regs(gh.decode())
            except Exception as e:                          # noqa: BLE001
                trace_lines.append(f"  {i:4d}  <step 失败 {e}>")
                return
            if len(rs) < 16:
                trace_lines.append(f"  {i:4d}  <g 解析失败>")
                return
            pc, r0, r2, r3 = rs[15], rs[0], rs[2], rs[3]
            trace_lines.append(f"  {i:4d}  0x{pc:08X}  {r2:#010x}  {r3:#010x}  {r0:#010x}")
            if pc in (0x088000BC, 0x088000C2, 0x088000D2):
                trace_lines.append(f"        ↑ 落在 0x{pc:08X}")
                break
        traced["done"] = True

    def on_hit(stop_pkt):
        nonlocal ncap
        try:
            gh = rsp.cmd("g")
        except Exception:                                   # noqa: BLE001
            gh = b""
        rs = regs(gh.decode()) if gh else []
        pc = rs[15] if len(rs) > 15 else -1
        with lock:
            if len(raw_stops) < 4:
                raw_stops.append(stop_pkt)
            hits[pc] += 1
            if rs:
                # 通用：记录 r3 / r2 / r0 的取值分布（哪个是「关注点」由标签说明）
                if len(rs) > 3:
                    dist[(pc, "r3")][rs[3]] += 1
                if len(rs) > 2:
                    dist[(pc, "r2")][rs[2]] += 1
                if len(rs) > 1:
                    dist[(pc, "r1")][rs[1]] += 1
                dist[(pc, "r0")][rs[0]] += 1
                if ncap < stop_cap and len(rs) >= 5:
                    samples[pc].append(tuple(rs[:5]))
                    ncap += 1
        if args.trace_at and pc == args.trace_at and not traced["done"]:
            do_trace()
        rsp.fire_and_forget("c")

    def pump():
        rsp.s.settimeout(0.2)
        while not stop.is_set():
            try:
                kind, val = rsp.token()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                return
            if kind != "pkt" or val[:1] not in (b"S", b"T"):
                continue
            on_hit(bytes(val[:12]))

    th = threading.Thread(target=pump, daemon=True)
    th.start()

    base = time.time() - t0
    press(base + 1.5, "DOWN")       # 设置页内移动光标 → 重画
    time.sleep(1.4)
    press(base + 4.0, "DOWN")
    time.sleep(1.4)
    press(base + 6.5, "UP")
    time.sleep(1.4)
    press(base + 9.0, "B")          # 退出设置页 → 菜单重画
    time.sleep(1.6)
    press(base + 12.0, "B")         # 退出菜单 → 回室内
    time.sleep(1.6)
    press(base + 15.0, "START")     # 再开菜单
    time.sleep(1.8)

    stop.set()
    time.sleep(0.4)

    print("\n===== 断点命中 =====")
    for addr in sorted(bps):
        print(f"  0x{addr:08X} {bps[addr][0]}  ×{hits.get(addr, 0)}")
    if hits.get(-1):
        print(f"  <PC 读取失败> ×{hits[-1]}")
    if raw_stops:
        print("  原始 stop 包:", [s.decode(errors='replace') for s in raw_stops])

    print("\n===== 寄存器真值分布 =====")
    for addr in sorted(bps):
        for rn in ("r3", "r2", "r1", "r0"):
            cnt = dist.get((addr, rn))
            if not cnt:
                continue
            txt = "  ".join(f"{v:#010x}×{n}" for v, n in cnt.most_common(4))
            mark = ""
            if addr == 0x0880009E and rn == "r3":
                mark = "   ← tpl = *(u32*)win"
            if addr == 0x088000B4 and rn == "r2":
                mark = "   ← tileData（门控比较值）"
            if addr == 0x088000C4 and rn == "r3":
                mark = "   ← tpl->textMode"
            if addr == 0x088000D2 and rn == "r0":
                mark = "   ← chs_canvas_base_for 返回值"
            print(f"  0x{addr:08X} {bps[addr][0]} {rn} = {txt}{mark}")

    if trace_lines:
        print("\n===== 单步跟踪 =====")
        for ln in trace_lines:
            print(ln)

    print("\n===== 首批样本 (r0,r1,r2,r3,r4) =====")
    for addr in sorted(samples):
        print(f"  [0x{addr:08X}] {bps[addr][0]} {bps[addr][1]}")
        for s in samples[addr][:4]:
            print("      " + " ".join(f"{v:08x}" for v in s))

    for addr in bps:
        try:
            rsp.fire_and_forget("z0,%x,2" % addr)
        except Exception:                                   # noqa: BLE001
            pass
    time.sleep(0.5)
    rsp.fire_and_forget("c")
    rsp.close()
    time.sleep(1.5)
    out_path, msg = md.capture(tag)
    print("\n[shot]", msg)
    md.kill_mgba()
    emu_log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
