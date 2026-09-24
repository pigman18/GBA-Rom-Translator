#!/usr/bin/env python3
"""B1 v4 最终采集 —— 加载 ss6（野外地图）savestate 直接进游戏，按键覆盖各场景。

v3 遗留（2026-09-20）：
  只走到「继续游戏」标题菜单（template@0x081BB544，MultistepLoadFont 整字库装载），
  tm0(0x08003542)/tm2(0x080033A2) 路径完全没覆盖 ⇒ 无法定 B-1/B-2/B-3。
  ⇒ 改用 -t 加载 ss6（callback1≈Overworld_PlaySpecialMapMusic ⇒ 野外地图）跳过开场。

断点（全部按 LR 分流统计）：
  DGT  0x08003630  DrawGlyphTiles      ← 4 个调用点
  IWTD 0x08002A50  InitWindowTileData  ← r0=template
  IWTDA 0x08002AA6 其内 bl 处           ← r4=template, r1=dst
  GCTN 0x08003708  GetCursorTileNum
  GGTP 0x08003730  GetGlyphTilePointers
  RK   0x0800047E  ReadKeys 注入点（按需挂）
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
OUTLOG = os.path.join(ROOT, ".tmp", "dgt_b1_v4.log")

BP_DGT = 0x08003630
BP_IWTD = 0x08002A50
BP_IWTDA = 0x08002AA6
BP_GCTN = 0x08003708
BP_GGTP = 0x08003730
BP_RK = 0x0800047E

GMAIN = 0x030016E0

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}

# BL 返回地址 → 归属（4 处调用点 +4）
DGT_CALL = {
    0x08002AAA: "IWTD/font0·4",
    0x08002B1A: "IWTD族2",
    0x080033A6: "tm2",
    0x08003546: "tm0",
}


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
        self.dgt_tpl = collections.Counter()
        self.tpl_info = {}
        self.gctn_info = {}

    def log(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()

    # ---------- 裸跑 ----------
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
            elif pc == BP_IWTDA:
                self.cnt["IWTDA"] += 1
            elif pc == BP_GCTN:
                self.on_gctn(regs)
            elif pc == BP_GGTP:
                self.cnt["GGTP"] += 1
        except GdbError:
            pass

    # ---------- 采集 ----------
    def on_dgt(self, regs):
        idx = regs.get("r0", 0)
        dst = regs.get("r1", 0)
        font = regs.get("r2", 0)
        width = regs.get("r3", 0)
        tpl = regs.get("r4", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["DGT"] += 1
        self.dgt_call[f"0x{lr:08X} {DGT_CALL.get(lr, '?')}"] += 1
        self.dgt_tpl[f"0x{tpl:08X}"] += 1
        k = ("dgt", lr, tpl, idx, dst, font)
        if k in self.seen:
            return
        self.seen.add(k)
        # 每个调用点只详录前 40 条
        n = self.dgt_call[f"0x{lr:08X} {DGT_CALL.get(lr, '?')}"]
        name = DGT_CALL.get(lr, f"LR=0x{lr:08X}")
        if n <= 40:
            tb = self.g.read_mem(tpl, 0x14)
            td = u32(tb, 0x0C) if len(tb) >= 0x10 else -1
            self.log(f"\n[DGT#{n} {name}] idx=0x{idx:X} dst=0x{dst:08X}"
                     f" font={font} w={width} tpl=0x{tpl:08X}")
            if len(tb) >= 0x14:
                self.log(f"  tm={tb[9]} cb={tb[1]} sb={tb[2]}"
                         f" tileData=0x{td:08X} tilemap=0x{u32(tb,0x10):08X}"
                         f" 砖号={(dst - td)//32 if td >= 0 else '?'}")

    def on_iwtd(self, regs):
        tpl = regs.get("r0", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["IWTD"] += 1
        tb = self.g.read_mem(tpl, 0x14)
        if len(tb) < 0x14:
            return
        k = ("iwtd", tpl, tb[8], tb[9])
        if k in self.seen:
            return
        self.seen.add(k)
        self.tpl_info[f"0x{tpl:08X}"] = (tb[1], tb[2], tb[8], tb[9],
                                         u32(tb, 0x0C), u32(tb, 0x10))
        self.log(f"\n[IWTD] tpl=0x{tpl:08X} LR=0x{lr:08X}"
                 f" cb={tb[1]} sb={tb[2]} font={tb[8]} tm={tb[9]}"
                 f" tileData=0x{u32(tb,0x0C):08X} tilemap=0x{u32(tb,0x10):08X}"
                 f" 字节={tb.hex(' ')}")

    def on_gctn(self, regs):
        win = regs.get("r0", 0)
        xo = regs.get("r1", 0)
        yo = regs.get("r2", 0)
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
        k = ("gctn", win, xo, yo, cx, cy, t)
        if k in self.seen:
            return
        self.seen.add(k)
        if len(self.gctn_info) < 60:
            self.log(f"\n[GCTN] win=0x{win:08X} xO={xo} yO={yo}"
                     f" → 砖号=0x{t:04X}@{a:08X} LR=0x{lr:08X}")
            self.log(f"  tm={wb[0x0A]} font={wb[0x0B]}"
                     f" TILE_BASE=0x{u16(wb,0x16):04X} TILE_OFF=0x{u16(wb,0x18):04X}"
                     f" tileData=0x{u32(wb,0x20):08X}")
            self.log(f"  text@0x{u32(wb,0x10):08X} index={u16(wb,0x14)}"
                     f" CUR TX={wb[0x1B]} X={wb[0x1A]} cx={cx}"
                     f" TY={wb[0x1D]} Y={wb[0x1C]} cy={cy}")
        self.gctn_info[f"0x{win:08X}"] = self.gctn_info.get(f"0x{win:08X}", 0) + 1

    # ---------- 按键 ----------
    def inject(self, key_seq, settle=0.6):
        self.g.set_sw_break(BP_RK)
        try:
            for k in key_seq:
                hit = False
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
                        hit = True
                        break
                    self._dispatch(regs)
                if hit and k:
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

    def tap(self, key, frames=3, settle=0.5):
        self.inject([key] * frames + [0] * 3, settle)

    def hold(self, key, frames=25, settle=0.8):
        self.inject([key] * frames + [0] * 3, settle)

    def summary(self):
        self.log("\n===== SUMMARY =====")
        for k, v in sorted(self.cnt.items()):
            self.log(f"  {k:10s} {v}")
        self.log("  --- DGT 调用点归属 ---")
        for k, v in self.dgt_call.most_common():
            self.log(f"    {k}  ×{v}")
        self.log("  --- DGT 的 template 分布 ---")
        for k, v in self.dgt_tpl.most_common(10):
            self.log(f"    {k}  ×{v}")
        self.log("  --- template 详情 ---")
        for k, v in self.tpl_info.items():
            self.log(f"    {k}: cb={v[0]} sb={v[1]} font={v[2]} tm={v[3]}"
                     f" tileData=0x{v[4]:08X} tilemap=0x{v[5]:08X}")
        self.log("  --- GCTN window 分布 ---")
        for k, v in sorted(self.gctn_info.items(), key=lambda x: -x[1])[:10]:
            self.log(f"    {k} ×{v}")
        self.f.close()


def main():
    fo = open(os.path.join(ROOT, ".tmp", "b1_v4.out"), "wb")
    p = subprocess.Popen([EXE, "-g", "-t", SS, ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[v4] mGBA pid={p.pid} 加载 ss6", flush=True)
    time.sleep(5)

    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    for a in (BP_DGT, BP_IWTD, BP_IWTDA, BP_GCTN, BP_GGTP):
        g.set_sw_break(a)
    print("[v4] 断点挂好", flush=True)

    b = B1(g)
    b.log(f"===== B1 v4（ss6 savestate）@ {time.strftime('%F %T')} =====")
    gm = g.read_mem(GMAIN, 0xC)
    b.log(f"gMain.callback1=0x{u32(gm,0):08X} callback2=0x{u32(gm,4):08X}")
    b.log(f"DISPCNT=0x{u32(g.read_mem(0x04000000,2),0):04X}")

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT, LEFT = KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"], KEYS["LEFT"]
    SELECT = KEYS["SELECT"]

    def step(label, fn):
        print(f"[v4] {label}", flush=True)
        b.log(f"\n\n########## {label} ##########")
        fn()
        b.log(f"  ↳ DGT={b.cnt['DGT']} IWTD={b.cnt['IWTD']} GCTN={b.cnt['GCTN']}"
              f" GGTP={b.cnt['GGTP']}")

    # 野外：走动（触发地图重绘 + 可能的 NPC 对话）
    step("原地裸跑 3s", lambda: b.run_bare(3.0))
    step("DOWN 长按", lambda: b.hold(DOWN, 30, 0.8))
    step("UP 长按", lambda: b.hold(UP, 30, 0.8))
    step("LEFT 长按", lambda: b.hold(LEFT, 30, 0.8))
    step("RIGHT 长按", lambda: b.hold(RIGHT, 30, 0.8))
    step("A 交互×5", lambda: [b.tap(A, 4, 1.0) for _ in range(5)])
    step("A 继续（对话翻页）", lambda: [b.tap(A, 4, 1.2) for _ in range(6)])
    # 开菜单 → 各页面
    step("START 开菜单", lambda: b.tap(START, 6, 1.8))
    step("DOWN", lambda: b.tap(DOWN, 5, 1.0))
    step("A 进页面", lambda: b.tap(A, 5, 2.0))
    step("页面内 DOWN×5", lambda: [b.tap(DOWN, 4, 0.8) for _ in range(5)])
    step("页面内 A×3", lambda: [b.tap(A, 4, 1.2) for _ in range(3)])
    step("B 返回×3", lambda: [b.tap(Bk, 4, 1.0) for _ in range(3)])
    step("START 开→DOWN×3→A", lambda: (b.tap(START, 6, 1.5),
                                       [b.tap(DOWN, 4, 0.7) for _ in range(3)],
                                       b.tap(A, 5, 2.0)))
    step("页面遍历 DOWN×8", lambda: [b.tap(DOWN, 4, 0.6) for _ in range(8)])
    step("B B", lambda: (b.tap(Bk, 4, 1.0), b.tap(Bk, 4, 1.0)))
    # 再往野外走远一点
    for i in range(2):
        step(f"野外补走 {i+1}", lambda: (b.hold(UP, 22, 0.5), b.hold(RIGHT, 22, 0.5),
                                         b.tap(A, 4, 1.0), b.hold(DOWN, 22, 0.5)))
    step("SELECT 尝试特殊菜单", lambda: (b.tap(SELECT, 5, 1.5),
                                        [b.tap(DOWN, 4, 0.7) for _ in range(3)],
                                        b.tap(Bk, 4, 1.0)))

    b.summary()
    print(f"[v4] 完成 → {OUTLOG}", flush=True)
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
