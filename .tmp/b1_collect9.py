#!/usr/bin/env python3
"""B1 采集 v9 —— 可靠注入 + callback 判据。

与 v3 的两个关键修正：
  1. 注入点从 0x0800047E 改为 0x0800043E（bics 之前），并同时写 r3 与 r2：
       r3 = key     ⇒ heldKeys / heldKeysRaw 的按位值
       r2 = 0       ⇒ heldKeysRaw 清 0 ⇒ newKeys = r3 & ~0 = r3
     旧点 0x0800047E 只在 strh r3,[r2,#0x28] 处改 r3，而 newKeys 早在 0x08000442
     就算完了 ⇒ 游戏永远收不到「刚按下」。（v3 采到 256 条是撞运气：
     它的 inject 循环每拍会重复命中多次，等价于连续按住若干帧。）
  2. 摘断点后再 cont，避免「cont 立刻被同一断点再次命中」⇒ 游戏根本没跑。

  3. 等待策略：不再盲等 6s，改为等 gMain+4 (callback1) 稳定非零后开始。

判据（全部可靠，不用 I/O 寄存器）：
  - gMain+0x2E newKeys（注入后一帧读）
  - pc 是否出现 DGT/IWTD/GCTN
  - callback 链
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
OUTLOG = os.path.join(ROOT, ".tmp", "dgt_b1_v9.log")

BP_DGT = 0x08003630
BP_IWTD = 0x08002A50
BP_IWTDA = 0x08002AA6
BP_GCTN = 0x08003708
BP_GGTP = 0x08003730
BP_RK = 0x0800043E          # ★ 改了（原 0x0800047E）

GMAIN = 0x030016E0

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}

CALLSITES = {
    0x08002AAA: "InitWindowTileData/tm1图集",
    0x08002B1A: "InitWindowTileData族2",
    0x080033A6: "tm2(glyphSpace2bpp)",
    0x08003546: "tm0(linear)",
}


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little") if len(b) >= o + 4 else -1


class B1:
    def __init__(self, g: GdbClient):
        self.g = g
        self.f = open(OUTLOG, "w", encoding="utf-8")
        self.seen = set()
        self.cnt = collections.Counter()
        self.fonts = collections.Counter()
        self.callers = collections.Counter()
        self.pcs = collections.Counter()

    def log(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()

    def gread(self, addr, n):
        try:
            return self.g.read_mem(addr, n)
        except GdbError:
            return b""

    def gmain(self, off, n=4):
        b = self.gread(GMAIN + off, n)
        return int.from_bytes(b, "little") if len(b) == n else -1

    def snap(self, tag):
        self.log(f"[{tag}] cb1=0x{self.gmain(4):08X} cb2=0x{self.gmain(8):08X}"
                 f" heldRaw=0x{self.gmain(0x28,2):04X} new=0x{self.gmain(0x2E,2):04X}")

    # ---- 断点处理 ----
    def _dispatch(self, pc, regs):
        try:
            if pc == BP_DGT:
                self.on_dgt(regs)
            elif pc == BP_IWTD:
                self.on_iwtd(regs)
            elif pc == BP_IWTDA:
                self.on_iwtda(regs)
            elif pc == BP_GCTN:
                self.cnt["GCTN"] += 1
            elif pc == BP_GGTP:
                self.cnt["GGTP"] += 1
        except GdbError:
            pass

    def run_bare(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.g.cont(timeout=0.25)
            except GdbError:
                pass
            try:
                regs = self.g.read_regs()
            except GdbError:
                continue
            pc = regs.get("r15", 0) & ~1
            self.pcs[pc] += 1
            self._dispatch(pc, regs)

    def on_iwtd(self, regs):
        tpl = regs.get("r0", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["IWTD"] += 1
        tb = self.gread(tpl, 0x14)
        if len(tb) < 0x14:
            return
        font = tb[8]
        k = (tpl, font, regs.get("r1", 0), regs.get("r2", 0))
        if k in self.seen:
            return
        self.seen.add(k)
        self.log(f"\n[IWTD] template@0x{tpl:08X} r1=0x{regs.get('r1',0):08X}"
                 f" r2=0x{regs.get('r2',0):08X} LR=0x{lr:08X}")
        self.log(f"  bgNum={tb[0]} charBase={tb[1]} screenBase={tb[2]}"
                 f" prio={tb[3]} fontNum={font} textMode={tb[9]}"
                 f" tileData=0x{u32(tb,0x0C):08X} tilemap=0x{u32(tb,0x10):08X}")
        self.log(f"  template 原始: {tb.hex(' ')}")

    def on_iwtda(self, regs):
        r4 = regs.get("r4", 0)
        self.cnt["IWTDA"] += 1
        tb = self.gread(r4, 0x14)
        font = tb[8] if len(tb) > 8 else -1
        self.fonts[f"font{font}"] += 1
        k = (r4, font, regs.get("r1", 0))
        if k in self.seen:
            return
        self.seen.add(k)
        self.log(f"\n[IWTDA→DGT] template@0x{r4:08X} font={font}"
                 f" 落点r1=0x{regs.get('r1',0):08X}")
        if len(tb) >= 0x14:
            self.log(f"  tileData=0x{u32(tb,0x0C):08X} tilemap=0x{u32(tb,0x10):08X}"
                     f" textMode={tb[9]}")
        self.log(f"  传参: r0(idx)=0x{regs.get('r0',0):08X}"
                 f" r2=0x{regs.get('r2',0):08X} r3=0x{regs.get('r3',0):08X}")

    def on_dgt(self, regs):
        idx = regs.get("r0", 0)
        dst = regs.get("r1", 0)
        font = regs.get("r2", 0)
        width = regs.get("r3", 0)
        tpl = regs.get("r4", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["DGT"] += 1
        self.callers[f"0x{lr:08X}"] += 1
        tb = self.gread(tpl, 0x14)
        td = u32(tb, 0x0C) if len(tb) >= 0x10 else -1
        tm = u32(tb, 0x10) if len(tb) >= 0x14 else -1
        k = (idx, dst, font, width, tpl)
        if k in self.seen:
            return
        self.seen.add(k)
        self.log(f"\n[DGT] idx=0x{idx:08X} dst=0x{dst:08X} font={font}"
                 f" width={width} tpl=0x{tpl:08X} LR=0x{lr:08X}"
                 f" [{CALLSITES.get(lr,'?')}]")
        if len(tb) >= 0x14:
            self.log(f"  template: bg={tb[0]} cb={tb[1]} sb={tb[2]}"
                     f" font={tb[8]} tm={tb[9]}"
                     f" tileData=0x{td:08X} tilemap=0x{tm:08X}")
            self.log(f"  → 砖号 = (dst-tileData)/32 = 0x{(dst-td)//32:04X}")

    # ---- 注入 ----
    def tap(self, key, press=3, release=3, settle=0.6):
        """★ 每拍：设断点 → 抓到帧 → 写 r3/r2 → 摘断点 → 跑一帧。"""
        self.kick([key] * press + [0] * release, settle)

    def kick(self, seq, settle=0.6):
        for k in seq:
            hit = False
            try:
                self.g.set_sw_break(BP_RK)
                for _ in range(40):
                    try:
                        self.g.cont(timeout=0.15)
                    except GdbError:
                        pass
                    try:
                        regs = self.g.read_regs()
                    except GdbError:
                        continue
                    pc = regs.get("r15", 0) & ~1
                    if pc == BP_RK:
                        hit = True
                        break
                    self._dispatch(pc, regs)
                if hit:
                    self.g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                    self.g.cmd("P2=00000000")
                    self.cnt["inject"] += 1
            except GdbError:
                pass
            finally:
                try:
                    self.g.clear_sw_break(BP_RK)
                except GdbError:
                    pass
            # 跑掉这一帧（此时 newKeys 已写入 gMain）
            try:
                self.g.cont(timeout=0.05)
            except GdbError:
                pass
        if settle > 0:
            self.run_bare(settle)

    def hold(self, key, frames=25, settle=1.0):
        self.kick([key] * frames + [0] * 3, settle)

    def summary(self):
        self.log("\n===== SUMMARY =====")
        for k, v in sorted(self.cnt.items()):
            self.log(f"  {k:16s} {v}")
        self.log("  --- DGT 调用点（LR）---")
        for k, v in self.callers.most_common():
            self.log(f"    {k}  {CALLSITES.get(int(k,16),'')}  ×{v}")
        self.log("  --- IWTD font 分布 ---")
        for k, v in self.fonts.most_common():
            self.log(f"    {k} ×{v}")
        self.log("  --- pc TOP 20 ---")
        for pc, c in self.pcs.most_common(20):
            self.log(f"    0x{pc:08X} ×{c}")
        self.f.close()


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "b1_v9.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[b1] mGBA pid={p.pid}", flush=True)
    time.sleep(4)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    for a in (BP_DGT, BP_IWTD, BP_IWTDA, BP_GCTN, BP_GGTP):
        g.set_sw_break(a)
    print("[b1] 常驻断点已设", flush=True)

    b = B1(g)
    b.log(f"===== B1 v9 采集 @ {time.strftime('%F %T')} =====")

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT, LEFT = (KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"], KEYS["LEFT"])

    def step(label, fn):
        print(f"[b1] {label}", flush=True)
        b.log(f"\n\n########## {label} ##########")
        fn()
        b.log(f"  ↳ DGT={b.cnt['DGT']} IWTD={b.cnt['IWTD']} IWTDA={b.cnt['IWTDA']}"
              f" GCTN={b.cnt['GCTN']} GGTP={b.cnt['GGTP']} inject={b.cnt['inject']}")
        b.snap("snap")

    step("裸跑 8s（等 callback 稳定）", lambda: b.run_bare(8.0))
    step("START 唤醒", lambda: b.tap(START, 6, 6, 2.0))
    step("A×3", lambda: [b.tap(A, 4, 4, 1.5) for _ in range(3)])
    step("DOWN 长按", lambda: b.hold(DOWN, 25, 1.2))
    step("A 确认", lambda: b.tap(A, 5, 5, 2.0))
    step("A×4 对话", lambda: [b.tap(A, 4, 4, 1.5) for _ in range(4)])
    step("START 开菜单", lambda: b.tap(START, 6, 6, 2.0))
    step("DOWN×2", lambda: [b.tap(DOWN, 5, 5, 1.0) for _ in range(2)])
    step("A 确认", lambda: b.tap(A, 5, 5, 2.0))
    step("B B 返回", lambda: [b.tap(Bk, 5, 5, 1.2) for _ in range(2)])
    for i in range(3):
        step(f"补走 {i+1}", lambda: (b.hold(DOWN, 18, 0.7), b.hold(RIGHT, 18, 0.7),
                                     b.tap(A, 4, 4, 1.5), b.hold(UP, 18, 0.7)))
    step("START→DOWN→A", lambda: (b.tap(START, 6, 6, 1.2), b.tap(DOWN, 5, 5, 1.0),
                                  b.tap(A, 5, 5, 2.0)))

    b.summary()
    print(f"[b1] 完成。日志: {OUTLOG}", flush=True)
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
