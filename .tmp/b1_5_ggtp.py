#!/usr/bin/env python3
"""B1.5 —— 采 GetGlyphTilePointers 的 (fontNum, idx) 全量分布。

目的：确认「官方 idx 上界」，从而判定中文字区（建议 idx 高 12 位 >= 0x1000）是否安全。

断点：GetGlyphTilePointers = 0x08003730
      入口 ABI: r0=fontNum(u8) r1=idx(u16) r2=&out0 r3=&out1
★ 入口 r0/r1 尚未被 u8/u16 裁剪，用 &0xFF / &0xFFFF 取。
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
OUTLOG = os.path.join(ROOT, ".tmp", "ggtp_b1_5.log")

BP_GGTP = 0x08003730
BP_RK = 0x0800043E
GMAIN = 0x030016E0

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}


class B15:
    def __init__(self, g: GdbClient):
        self.g = g
        self.f = open(OUTLOG, "w", encoding="utf-8")
        self.by_font: dict = collections.defaultdict(collections.Counter)
        self.total = 0
        self.hi = collections.Counter()      # idx >> 12

    def log(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()

    def on_ggtp(self, regs):
        font = regs.get("r0", 0) & 0xFF
        idx = regs.get("r1", 0) & 0xFFFF
        self.total += 1
        self.by_font[font][idx] += 1
        self.hi[(font, idx >> 12)] += 1

    def run(self, seconds):
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
            if regs.get("r15", 0) & ~1 == BP_GGTP:
                self.on_ggtp(regs)

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
                    if pc == BP_GGTP:
                        self.on_ggtp(regs)
                if hit:
                    self.g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                    self.g.cmd("P2=00000000")
            except GdbError:
                pass
            finally:
                try:
                    self.g.clear_sw_break(BP_RK)
                except GdbError:
                    pass
            try:
                self.g.cont(timeout=0.05)
            except GdbError:
                pass
        if settle > 0:
            self.run(settle)

    def tap(self, key, press=4, rel=4, settle=1.2):
        self.kick([key] * press + [0] * rel, settle)

    def report(self):
        self.log(f"\n===== GGTP 总命中 {self.total} =====")
        for font in sorted(self.by_font):
            c = self.by_font[font]
            idxs = sorted(c)
            self.log(f"\nfont {font}: {len(idxs)} 个不同 idx, 共 {sum(c.values())} 次")
            self.log(f"  idx 范围: 0x{min(idxs):04X} .. 0x{max(idxs):04X}")
            self.log(f"  idx>>12 分布: "
                     + ", ".join(f"0x{k:01X}×{v}"
                                 for k, v in sorted(collections.Counter(
                                     i >> 12 for i in idxs).items())))
            # 打印低位是否有非 0
            lo = collections.Counter(i & 0xF for i in idxs)
            self.log(f"  idx 低 4 位分布: "
                     + ", ".join(f"{k}×{v}" for k, v in sorted(lo.items())))
            sample = idxs[:24]
            self.log(f"  前 24 个 idx: " + " ".join(f"{i:03X}" for i in sample))
        self.log("\n=== 关键判定：官方 idx 最大值 ===")
        allidx = set()
        for c in self.by_font.values():
            allidx |= set(c)
        if allidx:
            self.log(f"  全局 idx 上界 = 0x{max(allidx):04X}")
            self.log(f"  idx >= 0x1000 的个数 = {sum(1 for i in allidx if i >= 0x1000)}")
        self.f.close()


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "b15.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[b15] pid={p.pid}", flush=True)
    time.sleep(4)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    g.set_sw_break(BP_GGTP)
    print("[b15] BP GetGlyphTilePointers 已设", flush=True)

    b = B15(g)
    b.log(f"===== B1.5 GGTP (fontNum, idx) 分布 @ {time.strftime('%F %T')} =====")

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT, LEFT = (KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"], KEYS["LEFT"])

    def step(label, fn):
        print(f"[b15] {label}", flush=True)
        b.log(f"\n##### {label} (累计 {b.total})")
        fn()
        b.log(f"  ↳ 累计 {b.total}")

    step("裸跑 8s", lambda: b.run(8.0))
    step("START→A×3 进游戏", lambda: (b.tap(START, 6, 6, 2.5),
                                     [b.tap(A, 4, 4, 1.8) for _ in range(3)]))
    step("DOWN + A", lambda: (b.kick([DOWN] * 25 + [0] * 3, 1.2), b.tap(A, 5, 5, 2.0)))
    step("A×4 对话", lambda: [b.tap(A, 4, 4, 1.5) for _ in range(4)])
    step("START 菜单", lambda: b.tap(START, 6, 6, 2.5))
    step("菜单 DOWN×3 / A", lambda: ([b.tap(DOWN, 5, 5, 1.2) for _ in range(3)],
                                     b.tap(A, 5, 5, 2.5)))
    step("子菜单 DOWN×4 / A", lambda: ([b.tap(DOWN, 4, 4, 1.2) for _ in range(4)],
                                       b.tap(A, 5, 5, 2.5)))
    step("B×3 返回", lambda: [b.tap(Bk, 4, 4, 1.5) for _ in range(3)])
    for i in range(4):
        step(f"走图 {i+1}", lambda: (b.kick([DOWN] * 20 + [0] * 3, 0.8),
                                     b.kick([RIGHT] * 20 + [0] * 3, 0.8),
                                     b.tap(A, 4, 4, 1.5),
                                     b.kick([UP] * 20 + [0] * 3, 0.8)))
    step("再开菜单遍历", lambda: (b.tap(START, 6, 6, 2.0),
                                  [b.tap(DOWN, 4, 4, 1.0) for _ in range(6)]))

    b.report()
    print(f"[b15] 完成 → {OUTLOG}", flush=True)
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
