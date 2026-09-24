#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_nav_canvas.py — 领航员画布/v8 一锤定音采样（2026-09-24）。

回答四个问题（全部有地址，零推断）：
  Q1 画布是否命中？        → canvas 记录槽 rec0/rec1 (win,tpl,base,w,h) + flag bit0 + 回落计数
  Q2 列表窗实际挂哪个 tpl？ → 断 InitTextPrinter (r0=win) 读 win[0x00] 模板指针
  Q3 v8 回落引擎实态？      → v8q (win,tpl) + CURSOR + PHASE
  Q4 重打印时 win 游标实值？ → 断重打印包装 0x0806F388 读 win[0x1A..0x1D]/text_ptr/idx

用法（先回退版 ROM：roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba）：
  1. mGBA 打开 ROM，进到领航员（可进训练家之眼）
  2. Tools → Start GDB stub (2345) → Pause
  3. python gdb/trace_nav_canvas.py --max 400
  4. Continue（F9）后操作：滚动列表 / 触发地名 marquee / 开关各页
  5. Ctrl-C 结束 → 看 gdb/nav_canvas.log
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from util.debug_patcher import GdbClient, GdbError  # noqa: E402

HOST, PORT = "127.0.0.1", 2345
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nav_canvas.log")

BP_INIT = 0x08002C68      # InitTextPrinter 入口（=hook 跳板首指令），r0=win
BP_REPRINT = 0x0806F388   # 原生重打印包装（领航员列表/marquee），r0=win(待证)

# EWRAM 状态区（game.h 权威）
A_V8_CURSOR, A_V8_PHASE = 0x0203FF42, 0x0203FF44
A_V8Q_MAGIC, A_V8Q_WIN, A_V8Q_TPL = 0x0203FF4A, 0x0203FF4C, 0x0203FF58
A_CV_MAGIC, A_CV_REC0, A_CV_REC1 = 0x0203FF5C, 0x0203FF5E, 0x0203FF6A
A_CV_FLAG, A_CV_FBCNT = 0x0203FF76, 0x0203FF77


def u16(b, o):
    return b[o] | (b[o + 1] << 8)


def u32(b, o):
    return b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)


def s16(b, o):
    v = u16(b, o)
    return v - 0x10000 if v >= 0x8000 else v


class Sampler:
    def __init__(self, gc):
        self.gc = gc
        self.log = open(LOG, "a", encoding="utf-8")
        self.hits = 0
        self.last_state = None
        self.last_key = None

    def w(self, line):
        stamp = time.strftime("%H:%M:%S")
        self.log.write(f"[{stamp}] {line}\n")
        self.log.flush()
        print(line)

    def dump_state(self, tag):
        g = self.gc
        b = g.read_mem(0x0203FF42, 0x38)  # FF42..FF7A 一把抓
        cur = u16(b, A_V8_CURSOR - 0x0203FF42)
        pha = u16(b, A_V8_PHASE - 0x0203FF42)
        qm = u16(b, A_V8Q_MAGIC - 0x0203FF42)
        qw = u32(b, A_V8Q_WIN - 0x0203FF42)
        qt = u32(b, A_V8Q_TPL - 0x0203FF42)
        cm = u16(b, A_CV_MAGIC - 0x0203FF42)
        r0w, r0t = u32(b, A_CV_REC0 - 0x0203FF42), u32(b, A_CV_REC0 + 4 - 0x0203FF42)
        r0b = u16(b, A_CV_REC0 + 8 - 0x0203FF42)
        r0wh = (b[A_CV_REC0 + 10 - 0x0203FF42], b[A_CV_REC0 + 11 - 0x0203FF42])
        r1w, r1t = u32(b, A_CV_REC1 - 0x0203FF42), u32(b, A_CV_REC1 + 4 - 0x0203FF42)
        r1b = u16(b, A_CV_REC1 + 8 - 0x0203FF42)
        r1wh = (b[A_CV_REC1 + 10 - 0x0203FF42], b[A_CV_REC1 + 11 - 0x0203FF42])
        flag = b[A_CV_FLAG - 0x0203FF42]
        fbc = b[A_CV_FBCNT - 0x0203FF42]
        return (cur, pha, qm, qw, qt, cm, r0w, r0t, r0b, r0wh, r1w, r1t, r1b,
                r1wh, flag, fbc)

    def fmt_state(self, s):
        (cur, pha, qm, qw, qt, cm, r0w, r0t, r0b, r0wh, r1w, r1t, r1b, r1wh,
         flag, fbc) = s
        lines = [
            f"  v8: cursor={cur} phase={pha}  v8q(magic={qm:#06x}): win={qw:#010x} tpl={qt:#010x}",
            f"  canvas(magic={cm:#06x}): rec0=win:{r0w:#010x} tpl:{r0t:#010x} base:{r0b} wh:{r0wh}"
            f" | rec1=win:{r1w:#010x} tpl:{r1t:#010x} base:{r1b} wh:{r1wh}",
            f"  canvas: flag={flag:#04x} (bit0_claim_fail={flag & 1}) fallback_cnt={fbc}",
        ]
        return "\n".join(lines)

    def dump_win(self, tag, win):
        if not (0x02000000 <= win < 0x02040000):
            self.w(f"{tag}: r0={win:#010x} 非EWRAM指针，跳过 win dump")
            return None
        b = self.gc.read_mem(win, 0x24)
        tpl = u32(b, 0x00)
        tm = b[0x0A]
        fn = b[0x0B]
        tptr = u32(b, 0x10)
        idx = u16(b, 0x14)
        toff = u16(b, 0x18)
        cx, ctx, cy, cty = b[0x1A], b[0x1B], b[0x1C], b[0x1D]
        self.w(f"{tag}: win={win:#010x} tpl={tpl:#010x} tm={tm} fn={fn} "
               f"text={tptr:#010x} idx={idx} tile_off={toff} "
               f"[1A..1D]=({cx},{ctx},{cy},{cty})")
        if 0x08000000 <= tpl < 0x08800000:
            t = self.gc.read_mem(tpl, 0x18)
            self.w(f"  tpl@{tpl:#010x}: cb={t[1]} sb={t[2]} font={t[8]} tm={t[9]} "
                   f"tileData={u32(t, 0x0C):#010x} tilemap={u32(t, 0x10):#010x}")
        return tpl

    def run(self, max_hits):
        g = self.gc
        g.set_sw_break(BP_INIT)
        g.set_sw_break(BP_REPRINT)
        self.w(f"=== trace_nav_canvas start (bps: ITP={BP_INIT:#x} REPRINT={BP_REPRINT:#x}) ===")
        try:
            while self.hits < max_hits:
                try:
                    g.cont(timeout=600.0)
                except GdbError as e:
                    self.w(f"cont 停止/超时: {e}")
                    if "超时" in str(e):
                        continue
                    break
                regs = g.read_regs()
                pc = regs.get("r15", 0) & ~1
                self.hits += 1
                if pc == BP_INIT:
                    self.dump_win("ITP", regs.get("r0", 0))
                elif pc == BP_REPRINT:
                    r0 = regs.get("r0", 0)
                    self.dump_win("REPRINT", r0)
                    if not (0x02000000 <= r0 < 0x02040000):
                        self.w(f"  regs: r0={regs.get('r0',0):#010x} r1={regs.get('r1',0):#010x} "
                               f"r2={regs.get('r2',0):#010x} r3={regs.get('r3',0):#010x} "
                               f"lr={regs.get('r14',0):#010x}")
                else:
                    self.w(f"HIT? pc={pc:#010x}")
                st = self.dump_state("")
                key = (pc, st)
                if key != self.last_key:
                    self.w(self.fmt_state(st))
                    self.last_key = key
        except KeyboardInterrupt:
            self.w("用户中断")
        finally:
            g.clear_sw_break(BP_INIT)
            g.clear_sw_break(BP_REPRINT)
            self.w(f"=== end, hits={self.hits}, log={LOG} ===")
            self.log.close()


def main():
    max_hits = 400
    for i, a in enumerate(sys.argv[1:]):
        if a == "--max":
            max_hits = int(sys.argv[i + 2])
    with GdbClient(HOST, PORT) as gc:
        Sampler(gc).run(max_hits)


if __name__ == "__main__":
    main()
