#!/usr/bin/env python3
"""B1 v3 —— 按实测 ABI 采集（修 v2 的参数误读）。

v2 血的教训（2026-09-20）：
  误以为日版 DrawGlyphTiles 是美版那种 (win, upperTile, ...)。
  反汇编 0x08002A50 (InitWindowTileData) 实证真实 ABI：
    8002a54: adds r4, r0, #0      ; r4 = 入参1 = **template 指针**（不是 window！）
    8002a56: lsls r1, r1, #16 / lsrs r3, r1, #16   ; r3 = 入参2 & 0xFFFF
    8002a5a: lsls r2, r2, #24 / lsrs r6, r2, #24   ; r6 = 入参3 & 0xFF = **index/计数器**
    8002a5e: ldrb r0, [r4, #8]    ; template->fontNum
    8002a60: cmp r0, #5 / bhi     ; fontNum>5 ⇒ 跳过
    8002a64: lsls/ldr/adds/ldr/mov pc  ; ★ 跳转表 @0x08002A70（6 项）
       fontNum 0/4 → 0x08002A8C → bl DrawGlyphTiles
       fontNum 1/3 → 0x08002AAC
       fontNum 2/5 → 0x08002ACC
    ⇒ DrawGlyphTiles 只在 fontNum∈{0,4} 被调。

  DrawGlyphTiles 入口真实 ABI：
    r0 = index（计数器，非 win！）
    r1 = 目标 VRAM 地址（tileData + 偏移）★ 落点
    r2 = fontNum
    r3 = 宽度/字节数
    [sp+0] = [template+6]
    [sp+4] = [template+7]
    r4 = **调用者的 r4 = template 指针** ⇒ [r4+8]=fontNum [r4+0xC]=tileData [r4+0x10]=tilemap

  ⇒ 判据(a) 直接结论：**钩内没有 window** ⇒ 「win[0x10]+win[0x14] 取当前字」在日版
     DrawGlyphTiles+2 处**取不到**。这是必须上报的方案修正点。
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
OUTLOG = os.path.join(ROOT, ".tmp", "dgt_b1_v7.log")

BP_DGT = 0x08003630
BP_IWTD = 0x08002A50    # InitWindowTileData 入口（拿 r0=template）
BP_IWTDA = 0x08002AA6   # InitWindowTileData 内 bl DrawGlyphTiles 处（拿 r4=template + r1=落点）
BP_GCTN = 0x08003708
BP_GGTP = 0x08003730
BP_RK = 0x0800047E

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


def u16(b: bytes, o: int) -> int:
    return b[o] | (b[o + 1] << 8) if len(b) >= o + 2 else -1


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little") if len(b) >= o + 4 else -1


class B1:
    def __init__(self, g: GdbClient):
        self.g = g
        self.f = open(OUTLOG, "w", encoding="utf-8")
        self.seen: set = set()
        self.cnt: collections.Counter = collections.Counter()
        self.fonts: collections.Counter = collections.Counter()
        self.callers: collections.Counter = collections.Counter()

    def log(self, s: str = "") -> None:
        self.f.write(s + "\n")
        self.f.flush()

    def run_bare(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.g.cont(timeout=0.30)
            except GdbError:
                pass
            try:
                regs = self.g.read_regs()
            except GdbError:
                continue
            pc = regs.get("r15", 0) & ~1
            self._dispatch(pc, regs)

    def _dispatch(self, pc: int, regs: dict) -> None:
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

    # ---- InitWindowTileData 入口：r0 = template ----
    def on_iwtd(self, regs: dict) -> None:
        tpl = regs.get("r0", 0)
        r1 = regs.get("r1", 0)
        r2 = regs.get("r2", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["IWTD"] += 1
        tb = self.g.read_mem(tpl, 0x14)
        if len(tb) < 0x14:
            return
        font = tb[8]
        td = u32(tb, 0x0C)
        tm = u32(tb, 0x10)
        k = (tpl, font, r1, r2)
        if k in self.seen:
            return
        self.seen.add(k)
        self.log(f"\n[IWTD] template@0x{tpl:08X} r1=0x{r1:08X} r2=0x{r2:08X}"
                 f" LR=0x{lr:08X}")
        self.log(f"  bgNum={tb[0]} charBase={tb[1]} screenBase={tb[2]}"
                 f" prio={tb[3]} fontNum={font} textMode={tb[9]}"
                 f" tileData=0x{td:08X} tilemap=0x{tm:08X}")
        self.log(f"  template 原始 0x14B: {tb.hex(' ')}")

    # ---- bl DrawGlyphTiles 前一瞬：r4 = template, r1 = 落点 ----
    def on_iwtda(self, regs: dict) -> None:
        r4 = regs.get("r4", 0)
        r0 = regs.get("r0", 0)
        r1 = regs.get("r1", 0)
        r2 = regs.get("r2", 0)
        r3 = regs.get("r3", 0)
        self.cnt["IWTDA"] += 1
        tb = self.g.read_mem(r4, 0x14)
        font = tb[8] if len(tb) > 8 else -1
        self.fonts[f"font{font}"] += 1
        k = (r4, font, r1)
        if k in self.seen:
            return
        self.seen.add(k)
        self.log(f"\n[IWTDA→DGT] template@0x{r4:08X} font={font}"
                 f" 落点r1=0x{r1:08X}")
        if len(tb) >= 0x14:
            self.log(f"  tileData=0x{u32(tb,0x0C):08X} tilemap=0x{u32(tb,0x10):08X}"
                     f" textMode={tb[9]}")
        self.log(f"  传参: r0(idx)=0x{r0:08X} r1(dst)=0x{r1:08X}"
                 f" r2=0x{r2:08X} r3=0x{r3:08X}")

    # ---- DrawGlyphTiles 入口（正确 ABI）----
    def on_dgt(self, regs: dict) -> None:
        idx = regs.get("r0", 0)
        dst = regs.get("r1", 0)
        font = regs.get("r2", 0)
        width = regs.get("r3", 0)
        tpl = regs.get("r4", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["DGT"] += 1
        self.callers[f"0x{lr:08X}"] += 1
        tb = self.g.read_mem(tpl, 0x14)
        td = u32(tb, 0x0C) if len(tb) >= 0x10 else -1
        tm = u32(tb, 0x10) if len(tb) >= 0x14 else -1
        k = (idx, dst, font, width, tpl)
        if k in self.seen:
            return
        self.seen.add(k)
        self.log(f"\n[DGT] idx=0x{idx:08X} dst=0x{dst:08X} font={font}"
                 f" width={width} tpl=0x{tpl:08X} LR=0x{lr:08X}"
                 f" [{CALLSITES.get(lr, '?')}]")
        if len(tb) >= 0x14:
            self.log(f"  template: bg={tb[0]} cb={tb[1]} sb={tb[2]}"
                     f" font={tb[8]} tm={tb[9]}"
                     f" tileData=0x{td:08X} tilemap=0x{tm:08X}")
            self.log(f"  → 砖号 = (dst - tileData)/32 = 0x{(dst - td) // 32:04X}"
                     f"  (tileData 相对序号)")
        self.log(f"  栈参 [sp+0]=0x{self._stk(regs, 0x28):08X}"
                 f" [sp+4]=0x{self._stk(regs, 0x2C):08X}")

    def _stk(self, regs: dict, off: int) -> int:
        sp = regs.get("r13", 0)
        try:
            return u32(self.g.read_mem(sp + off, 4), 0)
        except GdbError:
            return -1

    def inject(self, key_seq: list, settle: float = 0.5) -> None:
        self.g.set_sw_break(BP_RK)
        try:
            for k in key_seq:
                hit = False
                for _ in range(8):
                    try:
                        self.g.cont(timeout=0.12)
                    except GdbError:
                        pass
                    try:
                        regs = self.g.read_regs()
                    except GdbError:
                        break
                    pc = regs.get("r15", 0) & ~1
                    if pc == BP_RK:
                        hit = True
                        break
                    self._dispatch(pc, regs)
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

    def tap(self, key: int, frames: int = 3, settle: float = 0.5) -> None:
        self.inject([key] * frames + [0] * 3, settle)

    def hold(self, key: int, frames: int = 20, settle: float = 0.7) -> None:
        self.inject([key] * frames + [0] * 3, settle)

    def summary(self) -> None:
        self.log("\n===== SUMMARY =====")
        for k, v in sorted(self.cnt.items()):
            self.log(f"  {k:16s} {v}")
        self.log("  --- DGT 调用点（LR）---")
        for k, v in self.callers.most_common():
            self.log(f"    {k}  {CALLSITES.get(int(k,16),'')}  ×{v}")
        self.log("  --- IWTD font 分布 ---")
        for k, v in self.fonts.most_common():
            self.log(f"    {k} ×{v}")
        self.f.close()


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "b1_v7.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[b1] mGBA pid={p.pid}", flush=True)
    time.sleep(4)

    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    for a in (BP_DGT, BP_IWTD, BP_IWTDA, BP_GCTN, BP_GGTP):
        g.set_sw_break(a)
    print("[b1] 常驻断点: DGT/IWTD/IWTDA/GCTN/GGTP", flush=True)

    b = B1(g)
    b.log(f"===== B1 v3 采集 @ {time.strftime('%F %T')} =====")
    b.log("ABI 修正：r0=idx r1=dst r2=font r3=width r4=template（非 win）")

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT, LEFT = (KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"], KEYS["LEFT"])

    def step(label: str, fn) -> None:
        print(f"[b1] {label}", flush=True)
        b.log(f"\n\n########## {label} ##########")
        fn()
        b.log(f"  ↳ DGT={b.cnt['DGT']} IWTD={b.cnt['IWTD']} IWTDA={b.cnt['IWTDA']}"
              f" GCTN={b.cnt['GCTN']} GGTP={b.cnt['GGTP']}")

    step("启动裸跑 15s（等进标题/继续菜单）", lambda: b.run_bare(15.0))
    step("START×3", lambda: [b.tap(START, 6, 2.5) for _ in range(3)])
    step("A×4", lambda: [b.tap(A, 4, 2.0) for _ in range(4)])
    step("START", lambda: b.tap(START, 6, 2.5))
    step("A×3", lambda: [b.tap(A, 4, 2.0) for _ in range(3)])
    step("DOWN 长按", lambda: b.hold(DOWN, 25, 1.5))
    step("RIGHT 长按", lambda: b.hold(RIGHT, 25, 1.5))
    step("UP 长按", lambda: b.hold(UP, 25, 1.5))
    step("LEFT 长按", lambda: b.hold(LEFT, 25, 1.5))
    step("对话 A×6", lambda: [b.tap(A, 4, 1.5) for _ in range(6)])
    step("START 开菜单", lambda: b.tap(START, 6, 2.5))
    step("菜单 DOWN×3", lambda: [b.tap(DOWN, 5, 1.2) for _ in range(3)])
    step("菜单 A", lambda: b.tap(A, 5, 2.5))
    step("子菜单 DOWN×4", lambda: [b.tap(DOWN, 4, 1.2) for _ in range(4)])
    step("子菜单 A", lambda: b.tap(A, 5, 2.5))
    step("B 返回×3", lambda: [b.tap(Bk, 4, 1.5) for _ in range(3)])
    for i in range(3):
        step(f"补走 {i+1}", lambda: (b.hold(DOWN, 20, 0.8), b.hold(RIGHT, 20, 0.8),
                                     b.tap(A, 4, 1.5), b.hold(UP, 20, 0.8)))
    step("再开菜单 START→DOWN×2→A", lambda: (b.tap(START, 6, 2.0),
                                            [b.tap(DOWN, 4, 1.0) for _ in range(2)],
                                            b.tap(A, 5, 2.5)))
    step("遍历 DOWN×6", lambda: [b.tap(DOWN, 4, 1.0) for _ in range(6)])
    step("B BB", lambda: [b.tap(Bk, 4, 1.2) for _ in range(3)])

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
