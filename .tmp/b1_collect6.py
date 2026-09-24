#!/usr/bin/env python3
"""B1 v6 —— 从开机开始，用 callback1/callback2 做进度导航走到游戏内。

v5 教训（2026-09-20）：
  ss6 savestate 下按 START 无效（DGT 全 0），且 GDB 读 I/O 寄存器（DISPCNT/BG scroll）
  不可靠（读到 0x1F40/垃圾 hofs）⇒ 「用 BG scroll 验证按键」的结论作废。
  **唯一可靠的运行时判据 = gMain.callback1 / callback2**（v3/v4/v5 都读到合理 ROM 地址）。
  **唯一一次有效采集 = v3**：从开机走到「继续游戏」标题菜单（该菜单持续跑
  MultistepLoadFont 整字库装载 ⇒ 无需按键即稳定出数据）。

本版策略：从开机起，**每按一次键就读 callback1/callback2 并打印**，
  靠 callback2 的变化确认「真的推进了场景」，而不是盲按。
"""
from __future__ import annotations

import collections
import os
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
OUTLOG = os.path.join(ROOT, ".tmp", "dgt_b1_v6.log")

BP_DGT = 0x08003630
BP_IWTD = 0x08002A50
BP_GCTN = 0x08003708
BP_GGTP = 0x08003730
BP_RK = 0x0800047E
GMAIN = 0x030016E0

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080}

DGT_CALL = {0x08002AAA: "IWTD/font0·4", 0x08002B1A: "IWTD族2",
            0x080033A6: "tm2", 0x08003546: "tm0"}


def u16(b, o):
    return b[o] | (b[o + 1] << 8) if len(b) >= o + 2 else -1


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little") if len(b) >= o + 4 else -1


class B1:
    def __init__(self, g):
        self.g = g
        self.f = open(OUTLOG, "w", encoding="utf-8")
        self.seen = set()
        self.cnt = collections.Counter()
        self.dgt_call = collections.Counter()
        self.tpls = {}
        self.last_cb = None

    def log(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()

    def cbs(self):
        """读 callback1/callback2 —— 唯一可靠的场景判据。"""
        try:
            b = self.g.read_mem(GMAIN, 8)
            return (u32(b, 0), u32(b, 4))
        except GdbError:
            return (-1, -1)

    def run_bare(self, sec):
        end = time.time() + sec
        while time.time() < end:
            try:
                self.g.cont(timeout=0.25)
            except GdbError:
                pass
            try:
                self._dispatch(self.g.read_regs())
            except GdbError:
                pass

    def _dispatch(self, regs):
        pc = regs.get("r15", 0) & ~1
        try:
            if pc == BP_DGT:
                self.on_dgt(regs)
            elif pc == BP_IWTD:
                self.on_iwtd(regs)
            elif pc == BP_GCTN:
                self.on_gctn(regs)
            elif pc == BP_GGTP:
                self.cnt["GGTP"] += 1
        except GdbError:
            pass

    def on_dgt(self, regs):
        idx, dst = regs.get("r0", 0), regs.get("r1", 0)
        font, tpl = regs.get("r2", 0), regs.get("r4", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["DGT"] += 1
        name = DGT_CALL.get(lr, f"LR=0x{lr:08X}")
        k2 = f"0x{lr:08X} {name}"
        self.dgt_call[k2] += 1
        n = self.dgt_call[k2]
        k = ("d", lr, tpl, idx, dst)
        if k in self.seen or n > 60:
            return
        self.seen.add(k)
        tb = self.g.read_mem(tpl, 0x14)
        td = u32(tb, 0x0C) if len(tb) >= 0x10 else -1
        self.log(f"\n[DGT#{n} {name}] idx=0x{idx:X} dst=0x{dst:08X}"
                 f" font={font} tpl=0x{tpl:08X}")
        if len(tb) >= 0x14:
            self.log(f"  tm={tb[9]} cb={tb[1]} sb={tb[2]}"
                     f" tileData=0x{td:08X} tilemap=0x{u32(tb,0x10):08X}"
                     f" 砖号={(dst-td)//32 if td >= 0 else '?'}")

    def on_iwtd(self, regs):
        tpl = regs.get("r0", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["IWTD"] += 1
        tb = self.g.read_mem(tpl, 0x14)
        if len(tb) < 0x14:
            return
        k = ("i", tpl, tb[8], tb[9])
        if k in self.seen:
            return
        self.seen.add(k)
        self.tpls[f"0x{tpl:08X}"] = (tb[1], tb[2], tb[8], tb[9],
                                     u32(tb, 0x0C), u32(tb, 0x10))
        self.log(f"\n[IWTD] tpl=0x{tpl:08X} LR=0x{lr:08X} cb={tb[1]} sb={tb[2]}"
                 f" font={tb[8]} tm={tb[9]} tileData=0x{u32(tb,0x0C):08X}"
                 f" tilemap=0x{u32(tb,0x10):08X}")

    def on_gctn(self, regs):
        win, xo, yo = regs.get("r0", 0), regs.get("r1", 0), regs.get("r2", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["GCTN"] += 1
        wb = self.g.read_mem(win, 0x24)
        if len(wb) < 0x24:
            return
        cx = (wb[0x1B] + wb[0x1A]) & 0xFF
        cy = (wb[0x1D] + wb[0x1C]) & 0xFF
        tpl = u32(wb, 0)
        tma = u32(self.g.read_mem(tpl + 0x10, 4), 0) if tpl else 0
        a = (tma + (((cy + 32 * yo) << 5) + ((cx + xo) & 0xFF)) * 2) & 0xFFFFFFFF
        t = u16(self.g.read_mem(a, 2), 0)
        k = ("g", win, xo, yo, cx, cy, t)
        if k in self.seen:
            return
        self.seen.add(k)
        if self.cnt["GCTN"] <= 60:
            self.log(f"\n[GCTN] win=0x{win:08X} xO={xo} yO={yo} → 砖号=0x{t:04X}"
                     f"@{a:08X} LR=0x{lr:08X}")
            self.log(f"  tm={wb[0x0A]} font={wb[0x0B]}"
                     f" TILE_BASE=0x{u16(wb,0x16):04X} tileData=0x{u32(wb,0x20):08X}"
                     f" CUR cx={cx} cy={cy}")

    def inject(self, seq, settle=0.8):
        self.g.set_sw_break(BP_RK)
        try:
            for k in seq:
                for _ in range(10):
                    try:
                        self.g.cont(timeout=0.12)
                    except GdbError:
                        pass
                    try:
                        regs = self.g.read_regs()
                    except GdbError:
                        break
                    if (regs.get("r15", 0) & ~1) == BP_RK:
                        break
                    self._dispatch(regs)
                if k:
                    try:
                        self.g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                        self.cnt["inject"] += 1
                    except GdbError:
                        pass
        finally:
            try:
                self.g.clear_sw_break(BP_RK)
            except GdbError:
                pass
        if settle > 0:
            self.run_bare(settle)

    def press(self, key, settle=2.0):
        """松一帧 → 按 3 帧 → 松 → 跑 settle。"""
        self.inject([0, key, key, key, 0, 0], settle)

    def hold(self, key, frames=25, settle=0.8):
        self.inject([0, key] + [key] * frames + [0] * 3, settle)

    def summary(self):
        self.log("\n===== SUMMARY =====")
        for k, v in sorted(self.cnt.items()):
            self.log(f"  {k:10s} {v}")
        self.log("  --- DGT 调用点归属 ---")
        for k, v in self.dgt_call.most_common():
            self.log(f"    {k}  ×{v}")
        self.log("  --- template 详情 ---")
        for k, v in self.tpls.items():
            self.log(f"    {k}: cb={v[0]} sb={v[1]} font={v[2]} tm={v[3]}"
                     f" tileData=0x{v[4]:08X} tilemap=0x{v[5]:08X}")
        self.f.close()


def main():
    fo = open(os.path.join(ROOT, ".tmp", "b1_v6.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[v6] pid={p.pid} 从开机开始", flush=True)
    time.sleep(5)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    for a in (BP_DGT, BP_IWTD, BP_GCTN, BP_GGTP):
        g.set_sw_break(a)
    print("[v6] 断点挂好", flush=True)

    b = B1(g)
    b.log(f"===== B1 v6（开机导航）@ {time.strftime('%F %T')} =====")

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT, LEFT = KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"], KEYS["LEFT"]

    def nav(label, fn, settle=2.0):
        print(f"[v6] {label}", flush=True)
        c0 = b.cbs()
        b.log(f"\n\n########## {label} ##########")
        b.log(f"  按下前 callback1=0x{c0[0]:08X} callback2=0x{c0[1]:08X}")
        fn()
        c1 = b.cbs()
        b.log(f"  按下后 callback1=0x{c1[0]:08X} callback2=0x{c1[1]:08X}"
              f" {'★变化' if c0 != c1 else '（未变）'}")
        b.log(f"  ↳ DGT={b.cnt['DGT']} IWTD={b.cnt['IWTD']} GCTN={b.cnt['GCTN']}"
              f" GGTP={b.cnt['GGTP']}")
        return c1

    # 开机 → 标题（等 BIOS/logo）
    b.run_bare(8.0)
    print(f"[v6] 开机后 callback={b.cbs()}", flush=True)

    # 标题画面按 START / A 逐级推进，每步看 callback 变化
    for i in range(10):
        nav(f"推进按键 #{i+1} START", lambda: b.press(START, 2.5))
    for i in range(8):
        nav(f"推进按键 #{i+1} A", lambda: b.press(A, 2.5))
    for i in range(4):
        nav(f"补 START #{i+1}", lambda: b.press(START, 2.5))

    # 进入后：走动 + 开菜单
    nav("长按 DOWN", lambda: b.hold(DOWN, 30, 1.0))
    nav("按 START 开菜单", lambda: b.press(START, 3.0))
    nav("菜单 DOWN", lambda: b.press(DOWN, 2.0))
    nav("菜单 A", lambda: b.press(A, 3.0))
    nav("B 返回", lambda: b.press(Bk, 2.0))
    nav("B 再返回", lambda: b.press(Bk, 2.0))
    for i in range(6):
        nav(f"A 交互 #{i+1}", lambda: b.press(A, 2.0))
    nav("RIGHT 走", lambda: b.hold(RIGHT, 30, 1.0))
    nav("再开菜单", lambda: b.press(START, 2.5))
    for i in range(6):
        nav(f"菜单 DOWN #{i+1}", lambda: b.press(DOWN, 1.5))
    nav("菜单 A 确认", lambda: b.press(A, 3.0))
    nav("退出 BBB", lambda: [b.press(Bk, 1.5) for _ in range(3)])

    b.summary()
    print(f"[v6] 完成 → {OUTLOG}", flush=True)
    g.close()
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()
    fo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
