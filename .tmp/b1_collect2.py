#!/usr/bin/env python3
"""B1 正式采集器 v2 —— 按需挂/摘 ReadKeys 断点（修 v1 的拖慢问题）。

v1 教训（2026-09-20）：
  ReadKeys 每帧都被调 ⇒ 常挂 RK 断点会让循环速率＝RK 命中速率（20Hz），
  游戏被拖到 1/3 速度，且 cont() 一停就停在同一处 ⇒ DGT/GCTN 永远轮不到。
  ⇒ 必须「按需挂、用完即摘」。

正确节奏：
  平时：只挂 DGT/GCTN/GGTP，游戏裸跑（cont 超时属正常）
  按键：挂 RK → 连打 N 拍（每拍约 1 帧）→ 摘 RK → 裸跑 0.5~1.5s 让游戏响应

已知实证（本会话）：
  · gMain = 0x030016E0（反汇编 + 运行期 r2 双证；符号表 0x03001770 是错的）
  · ReadKeys = 0x0800042C；注入点 = 0x0800047E (`strh r3,[r2,#0x28]`)
  · 改 r3（'P3=...'）⇒ gMain.heldKeys 真的变（heldKeys=0x0008 实证）
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
OUTLOG = os.path.join(ROOT, ".tmp", "dgt_b1_gdb.log")

BP_DGT = 0x08003630
BP_GCTN = 0x08003708
BP_GGTP = 0x08003730
BP_RK = 0x0800047E

GMAIN = 0x030016E0

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}

CALLSITES = {
    0x08002AA6: "InitWindowTileData/tm1图集",
    0x08002B16: "InitWindowTileData族",
    0x080033A2: "tm2(glyphSpace2bpp)",
    0x08003542: "tm0(linear)",
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
        self.callers: collections.Counter = collections.Counter()
        self.modes: collections.Counter = collections.Counter()
        self.gctn_samples: list = []
        self.tilenum_seq: list = []   # 砖号推进序列（判据 b）
        self._phase: list = []

    def log(self, s: str = "") -> None:
        self.f.write(s + "\n")
        self.f.flush()

    # ---------- 裸跑：只等 DGT/GCTN/GGTP ----------
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
            if pc == BP_DGT:
                try:
                    self.on_dgt(regs)
                except GdbError as e:
                    self.log(f"  !! DGT err: {e}")
            elif pc == BP_GCTN:
                try:
                    self.on_gctn(regs)
                except GdbError:
                    pass
            elif pc == BP_GGTP:
                self.cnt["GGTP"] += 1

    # ---------- 按键：挂 RK → 连打 → 摘 RK ----------
    def inject(self, key_seq: list[int], settle: float = 0.6) -> None:
        """key_seq：每拍一个键值（0=空）。打完摘断点，裸跑 settle 秒。"""
        self.g.set_sw_break(BP_RK)
        try:
            for k in key_seq:
                # 等一帧（RK 命中）
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
                    if pc == BP_DGT:
                        try:
                            self.on_dgt(regs)
                        except GdbError:
                            pass
                    elif pc == BP_GCTN:
                        try:
                            self.on_gctn(regs)
                        except GdbError:
                            pass
                if hit and k:
                    try:
                        self.g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                        self.cnt["inject"] += 1
                    except GdbError:
                        pass
                elif hit:
                    self.cnt["inject_idle"] += 1
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

    # ---------- 采集 ----------
    def on_dgt(self, regs: dict) -> None:
        win = regs.get("r0", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["DGT"] += 1
        self.callers[f"0x{lr:08X}"] += 1
        wb = self.g.read_mem(win, 0x24)
        if len(wb) < 0x24:
            return
        idx = u16(wb, 0x14)
        tptr = u32(wb, 0x10)
        textm = wb[0x0A]
        font = wb[0x0B]
        self.modes[f"tm{textm}/font{font}"] += 1
        k = (win, idx, textm, font)
        if k in self.seen:
            return
        self.seen.add(k)
        cur = (tptr + idx) & 0xFFFFFFFF
        raw = self.g.read_mem(cur, 8)
        tdb = u32(wb, 0x20)
        t0, a0 = self.cur_tile(win, wb, 0, 0)
        t1, a1 = self.cur_tile(win, wb, 0, 1)
        call = CALLSITES.get(lr, f"LR=0x{lr:08X}")
        lead, trail = (wb[0x0E], wb[0x0F]) if len(wb) > 0x0F else (-1, -1)
        self.log(f"\n[DGT] win=0x{win:08X} LR=0x{lr:08X} [{call}]")
        self.log(f"  tm={textm} font={font} index={idx}"
                 f" TILE_BASE=0x{u16(wb,0x16):04X} TILE_OFF=0x{u16(wb,0x18):04X}"
                 f" tileData=0x{tdb:08X}")
        self.log(f"  字形: lead=0x{lead:02X} trail=0x{trail:02X}"
                 f" idx(lead<<8|trail)=0x{(lead<<8|trail) & 0xFFFF:04X}")
        self.log(f"  CUR: TX={wb[0x1B]} X={wb[0x1A]} → cx={(wb[0x1B]+wb[0x1A])&0xFF}"
                 f" | TY={wb[0x1D]} Y={wb[0x1C]} → cy={(wb[0x1D]+wb[0x1C])&0xFF}")
        self.log(f"  当前字@0x{cur:08X} 字节={raw.hex(' ')} ↳ {self._show(raw)}")
        self.log(f"  官方砖号 TL=0x{t0:04X}@{a0:08X} BL=0x{t1:04X}@{a1:08X}"
                 f" ΔBL-TL={t1 - t0 if t0 >= 0 and t1 >= 0 else '?'}"
                 f" 落点TL=0x{(tdb + 32 * t0) & 0xFFFFFFFF:08X}")

    def on_gctn(self, regs: dict) -> None:
        win = regs.get("r0", 0)
        xo = regs.get("r1", 0)
        yo = regs.get("r2", 0)
        lr = regs.get("r14", 0) & ~1
        self.cnt["GCTN"] += 1
        # 只采 yOff==0 的（上半砖）用于砖号推进序列
        if yo not in (0, 1):
            return
        wb = self.g.read_mem(win, 0x24)
        if len(wb) < 0x24:
            return
        t, a = self.cur_tile(win, wb, xo, yo)
        key = (win, xo, yo, wb[0x1A], wb[0x1B], wb[0x1C], wb[0x1D], t)
        if key in self.seen:
            return
        self.seen.add(key)
        self.log(f"\n[GCTN] win=0x{win:08X} xOff={xo} yOff={yo}"
                 f" → 砖号=0x{t:04X} @0x{a:08X} LR=0x{lr:08X}")
        self.log(f"  CUR TX={wb[0x1B]} X={wb[0x1A]} cx={(wb[0x1B]+wb[0x1A])&0xFF}"
                 f" TY={wb[0x1D]} Y={wb[0x1C]} cy={(wb[0x1D]+wb[0x1C])&0xFF}")

    def cur_tile(self, win: int, wb: bytes, xo: int, yo: int):
        cx = (wb[0x1B] + wb[0x1A]) & 0xFF
        cy = (wb[0x1D] + wb[0x1C]) & 0xFF
        tpl = u32(wb, 0)
        tm = u32(self.g.read_mem(tpl + 0x10, 4), 0) if tpl else 0
        row = (cy + 32 * yo) & 0xFFFF
        col = (cx + xo) & 0xFF
        a = (tm + ((row << 5) + col) * 2) & 0xFFFFFFFF
        return u16(self.g.read_mem(a, 2), 0), a

    def _show(self, raw: bytes) -> str:
        if len(raw) < 2:
            return "?"
        c = raw[0]
        if c == 0xF9:
            return f"<双字节 F9{raw[1]:02X}{raw[2]:02X}>"
        if c == 0xF8:
            return f"<控制 F8{raw[1]:02X}>"
        if c == 0xFC:
            return f"<控制 FC{raw[1]:02X}{raw[2]:02X}>"
        if c == 0xFD:
            return f"<FCB F9? {raw[1]:02X}>"
        if c == 0xFF:
            return "<串结束>"
        if c == 0xFA:
            return "<换行>"
        return f"byte 0x{c:02X}"

    def summary(self) -> None:
        self.log("\n===== SUMMARY =====")
        for k, v in sorted(self.cnt.items()):
            self.log(f"  {k:16s} {v}")
        self.log("  --- DGT 调用点分布 ---")
        for k, v in self.callers.most_common():
            self.log(f"    {k}  {CALLSITES.get(int(k, 16), '')}  ×{v}")
        self.log("  --- DGT textMode/font 分布 ---")
        for k, v in self.modes.most_common():
            self.log(f"    {k}  ×{v}")
        self.f.close()


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "b1_sdl.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[b1] mGBA pid={p.pid}", flush=True)
    time.sleep(4)

    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    for a in (BP_DGT, BP_GCTN, BP_GGTP):
        g.set_sw_break(a)
    print("[b1] 常驻断点: DGT/GCTN/GGTP（RK 按需挂）", flush=True)

    b = B1(g)
    b.log(f"===== B1 v2 采集 @ {time.strftime('%F %T')} =====")
    b.log(f"gMain=0x{GMAIN:08X} 注入点=ReadKeys 0x{BP_RK:08X}（按需挂）")

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT, LEFT = (KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"],
                             KEYS["LEFT"])

    def step(label: str, fn) -> None:
        print(f"[b1] {label}", flush=True)
        b.log(f"\n\n########## {label} ##########")
        fn()
        b.log(f"  ↳ 统计: DGT={b.cnt['DGT']} GCTN={b.cnt['GCTN']} GGTP={b.cnt['GGTP']}")

    # 1) 先裸跑让游戏启动到标题
    step("启动裸跑 6s", lambda: b.run_bare(6.0))
    # 2) 过标题/继续
    step("按 START", lambda: (b.tap(START, 6, 2.0)))
    step("按 A×3", lambda: (b.tap(A, 4, 1.2), b.tap(A, 4, 1.2), b.tap(A, 4, 1.5)))
    # 3) 进游戏后走动
    step("按住 DOWN", lambda: b.hold(DOWN, 25, 1.0))
    step("按住 RIGHT", lambda: b.hold(RIGHT, 25, 1.0))
    step("按住 UP", lambda: b.hold(UP, 25, 1.0))
    step("按住 LEFT", lambda: b.hold(LEFT, 25, 1.0))
    # 4) 交互（对话）
    step("对话 A×4", lambda: [b.tap(A, 4, 1.0) for _ in range(4)])
    # 5) 开菜单
    step("开菜单 START", lambda: b.tap(START, 6, 1.5))
    step("菜单 DOWN×2", lambda: (b.tap(DOWN, 5, 0.8), b.tap(DOWN, 5, 0.8)))
    step("菜单 A", lambda: b.tap(A, 5, 1.5))
    step("菜单 B 返回", lambda: (b.tap(Bk, 5, 0.8), b.tap(Bk, 5, 1.2)))
    # 6) 再来一轮走动 + 交互，制造更多字
    for i in range(3):
        step(f"补走 {i+1}", lambda: (
            b.hold(DOWN, 18, 0.6), b.hold(RIGHT, 18, 0.6),
            b.tap(A, 4, 1.2), b.hold(UP, 18, 0.6)))
    # 7) 尝试开背包/宝可梦菜单
    step("START→DOWN→A", lambda: (b.tap(START, 6, 1.0), b.tap(DOWN, 5, 0.8),
                                  b.tap(A, 5, 2.0)))
    step("再按 B×2", lambda: (b.tap(Bk, 5, 1.0), b.tap(Bk, 5, 1.0)))

    b.summary()
    print(f"[b1] 完成。日志: {OUTLOG}", flush=True)
    try:
        print(f"[b1] DISPCNT=0x{int.from_bytes(g.read_mem(0x04000000,2),'little'):04X}"
              f" heldKeys=0x{int.from_bytes(g.read_mem(GMAIN+0x2C,2),'little'):04X}",
              flush=True)
    except GdbError:
        pass
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
