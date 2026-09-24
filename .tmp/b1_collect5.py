#!/usr/bin/env python3
"""B1 v5 —— ss6 加载 + 长按 START 开菜单（菜单必画字）。

v4 教训：按键已实证有效（BG scroll 0x30B8→0x8593 = 角色真的走了），
  但 A 键对话 0 命中 ⇒ 位置无 NPC 或 newKeys 时序问题。
  ⇒ 改为「开菜单」这条必画字的路（v3 已证明 START 能开菜单）。

关键修正（newKeys 时序）：
  ReadKeys 里 newKeys = keyInput & ~heldKeysRaw。
  我改 r3 后，heldKeysRaw 立刻变成 r3 ⇒ 连续注入同一个键时 newKeys 恒 0。
  ⇒ 想产生「刚按下」必须夹一拍松开：注入序列 = [0] + [key]*N + [0]*M
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
SS = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.ss6")
OUTLOG = os.path.join(ROOT, ".tmp", "dgt_b1_v5.log")

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

    def log(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()

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
        key = f"0x{lr:08X} {name}"
        self.dgt_call[key] += 1
        n = self.dgt_call[key]
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
        if self.cnt["GCTN"] <= 50:
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
        """★ 先松一帧清 heldKeysRaw，再按——保证产生 newKeys。"""
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
    fo = open(os.path.join(ROOT, ".tmp", "b1_v5.out"), "wb")
    p = subprocess.Popen([EXE, "-g", "-t", SS, ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[v5] pid={p.pid} 加载 ss6", flush=True)
    time.sleep(5)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    for a in (BP_DGT, BP_IWTD, BP_GCTN, BP_GGTP):
        g.set_sw_break(a)
    print("[v5] 断点挂好", flush=True)

    b = B1(g)
    b.log(f"===== B1 v5（ss6）@ {time.strftime('%F %T')} =====")
    b.log(f"callback1=0x{u32(g.read_mem(GMAIN,4),0):08X}"
          f" callback2=0x{u32(g.read_mem(GMAIN+4,4),0):08X}")

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT, LEFT = KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"], KEYS["LEFT"]

    def step(label, fn):
        print(f"[v5] {label}", flush=True)
        b.log(f"\n\n########## {label} ##########")
        fn()
        b.log(f"  ↳ DGT={b.cnt['DGT']} IWTD={b.cnt['IWTD']} GCTN={b.cnt['GCTN']}"
              f" GGTP={b.cnt['GGTP']}")

    step("裸跑 2s", lambda: b.run_bare(2.0))
    # 走动确认游戏响应
    step("长按 DOWN", lambda: b.hold(DOWN, 30, 1.0))
    step("长按 UP", lambda: b.hold(UP, 30, 1.0))
    # ★ 开菜单（必画字）
    step("★按 START 开菜单", lambda: b.press(START, 3.0))
    step("菜单 DOWN", lambda: b.press(DOWN, 1.5))
    step("菜单 DOWN", lambda: b.press(DOWN, 1.5))
    step("菜单 A 确认", lambda: b.press(A, 3.0))
    step("子菜单 DOWN", lambda: (b.press(DOWN, 1.2), b.press(DOWN, 1.2)))
    step("子菜单 A", lambda: b.press(A, 3.0))
    step("B 返回", lambda: b.press(Bk, 2.0))
    step("B 再返回", lambda: b.press(Bk, 2.0))
    # 再开一次，走更多项
    step("★再开菜单", lambda: b.press(START, 2.5))
    step("遍历 DOWN×6", lambda: [b.press(DOWN, 1.0) for _ in range(6)])
    step("A 进项", lambda: b.press(A, 3.0))
    step("B B B 退出", lambda: [b.press(Bk, 1.2) for _ in range(3)])
    # 野外交互
    step("A×6（对话尝试）", lambda: [b.press(A, 1.5) for _ in range(6)])
    step("野外走一圈", lambda: (b.hold(RIGHT, 25, 0.6), b.hold(DOWN, 25, 0.6),
                                b.hold(LEFT, 25, 0.6), b.hold(UP, 25, 0.6)))

    b.summary()
    print(f"[v5] 完成 → {OUTLOG}", flush=True)
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
