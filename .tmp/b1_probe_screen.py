#!/usr/bin/env python3
"""B1 诊断 —— 游戏到底停在哪个画面？

问题：v3（唯一有效）采到 256 条 DGT，v7/v8（同流程重跑）全 0。
现象：v8 的 inject=365（按键进去了），但 GCTN=0（连画版权文字都没有）。
⇒ 需要知道游戏是否真的「在跑」，以及停在哪。

采集内容（全是可靠判据，不用 I/O 寄存器）：
  1. pc 采样直方图（前 N 次）—— 游戏是否在推进
  2. gMain 按键状态（+0x28 heldKeysRaw 等）—— 按键是否真进去
  3. callback 链（gMain+4/+8）—— 官方认画面阶段的方式
  4. DISPCNT / 前 4 个字 —— 只做参考，不下结论
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
OUT = os.path.join(ROOT, ".tmp", "probe_screen.out")

GMAIN = 0x030016E0
BP_RK = 0x0800047E
BP_DGT = 0x08003630

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}


class Probe:
    def __init__(self, g: GdbClient):
        self.g = g
        self.f = open(OUT, "w", encoding="utf-8")
        self.pcs: collections.Counter = collections.Counter()
        self.n_dgt = 0

    def log(self, s: str = "") -> None:
        self.f.write(s + "\n")
        self.f.flush()

    def u32(self, addr: int) -> int:
        try:
            return int.from_bytes(self.g.read_mem(addr, 4), "little")
        except GdbError:
            return -1

    def snapshot(self, tag: str) -> None:
        try:
            regs = self.g.read_regs()
        except GdbError:
            self.log(f"[{tag}] read_regs 失败")
            return
        pc = regs.get("r15", 0)
        self.pcs[pc & ~1] += 1
        if pc & ~1 == BP_DGT:
            self.n_dgt += 1
        try:
            gm = self.g.read_mem(GMAIN, 0x40)
        except GdbError:
            self.log(f"[{tag}] gMain 读失败")
            return
        def u16(o):
            return gm[o] | (gm[o + 1] << 8) if len(gm) >= o + 2 else -1
        self.log(
            f"[{tag}] pc=0x{pc:08X}"
            f" cb1=0x{int.from_bytes(gm[4:8],'little'):08X}"
            f" cb2=0x{int.from_bytes(gm[8:12],'little'):08X}"
            f" heldRaw=0x{u16(0x28):04X} newRaw=0x{u16(0x2A):04X}"
            f" held=0x{u16(0x2C):04X} new=0x{u16(0x2E):04X}"
            f" newRep=0x{u16(0x30):04X}"
        )

    def run(self, seconds: float, tag: str, every: float = 0.5) -> None:
        end = time.time() + seconds
        n = 0
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
            n += 1
            if pc == BP_DGT:
                self.n_dgt += 1
            if n % 8 == 0:
                self.snapshot(f"{tag}#{n}")

    def inject(self, key_seq: list, settle: float = 0.5) -> None:
        self.g.set_sw_break(BP_RK)
        try:
            for k in key_seq:
                for _ in range(10):
                    try:
                        self.g.cont(timeout=0.15)
                    except GdbError:
                        pass
                    try:
                        regs = self.g.read_regs()
                    except GdbError:
                        break
                    if regs.get("r15", 0) & ~1 == BP_RK:
                        if k:
                            try:
                                self.g.cmd(
                                    f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                            except GdbError:
                                pass
                        break
        finally:
            try:
                self.g.clear_sw_break(BP_RK)
            except GdbError:
                pass
        if settle > 0:
            self.run(settle, "settle")

    def tap(self, key: int, frames: int = 4, settle: float = 1.0) -> None:
        self.inject([key] * frames + [0] * 3, settle)

    def report(self) -> None:
        self.log("\n===== PC 直方图 TOP 25 =====")
        for pc, c in self.pcs.most_common(25):
            self.log(f"  0x{pc:08X}  ×{c}")
        self.log(f"\nDGT 命中 = {self.n_dgt}")
        self.log(f"distinct pc = {len(self.pcs)}")
        self.f.close()


def main() -> int:
    fo = open(OUT + ".mgba", "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[probe] mGBA pid={p.pid}", flush=True)
    time.sleep(4)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    pr = Probe(g)
    pr.log(f"===== 画面探测 @ {time.strftime('%F %T')} =====")

    print("[probe] 裸跑 8s 采样", flush=True)
    pr.run(8.0, "boot")
    pr.snapshot("after-boot")

    print("[probe] START → 8s", flush=True)
    pr.tap(KEYS["START"], 6, 3.0)
    pr.snapshot("after-START")

    print("[probe] A×3 → 8s", flush=True)
    for _ in range(3):
        pr.tap(KEYS["A"], 5, 2.0)
    pr.snapshot("after-A3")

    print("[probe] DOWN 长按", flush=True)
    pr.inject([KEYS["DOWN"]] * 30 + [0] * 3, 2.0)

    print("[probe] A×4 对话", flush=True)
    for _ in range(4):
        pr.tap(KEYS["A"], 5, 2.0)
    pr.snapshot("after-dialog")

    print("[probe] START 菜单", flush=True)
    pr.tap(KEYS["START"], 6, 3.0)
    pr.snapshot("after-menu")

    pr.report()
    print(f"[probe] 完成 → {OUT}", flush=True)
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
