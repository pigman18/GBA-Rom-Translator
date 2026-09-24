#!/usr/bin/env python3
"""B1 采集（GDB 注入版）：不依赖窗口焦点，直接经 GDB stub 注入按键 + 采数据。

为什么不用 SendInput：
  后台会话里 `SetForegroundWindow` 静默失败 ⇒ 合成按键到不了 mGBA，
  模拟器停在标题/继续菜单不动（2026-09-20 实测：237fps 裸跑、日志 20 行即静止）。

本方案：
  1. mGBA -g 起，patcher 作为**子进程**同生命周期跑（不探测端口，避免抢单客户端槽）
  2. 另开一条 GDB 连接？**不行** —— mGBA stub 只接一个客户端。
     ⇒ 所以驱动逻辑**并入 patcher 进程**：用 patcher 的 Ctx 回调，在两次 continue
        之间写 REG_KEYINPUT 注入按键。
     简化实现：本脚本**自己**当 GDB 客户端（不用 gdb_patcher），
     复用 debug_patcher.GdbClient + 自己的断点循环 + 自己的 handler。

GBA 按键（REG_KEYINPUT 0x04000130）低 10 位，**0 = 按下**：
  A=0x0001 B=0x0002 SELECT=0x0004 START=0x0008 RIGHT=0x0010 LEFT=0x0020
  UP=0x0040 DOWN=0x0080 R=0x0100 L=0x0200
  其余位常 1 ⇒ 空闲值 0x03FF
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
sys.path.insert(0, os.path.join(ROOT, "src"))

from debug_patcher import GdbClient  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
OUTLOG = os.path.join(ROOT, ".tmp", "dgt_b1_gdb.log")
DETACHED = 0x00000008 | 0x00000200

KEY = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
       "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
       "R": 0x0100, "L": 0x0200}
IDLE = 0x03FF

KEYINPUT = 0x04000130

# --- 断点 ---
BREAKS = {
    0x08003630: "DrawGlyphTiles",
    0x08003708: "GetCursorTileNum",
    0x08003730: "GetGlyphTilePointers",
    0x08002C68: "InitTextPrinter",
    0x080032F8: "PrintNextChar",
    0x08002A50: "InitWindowTileData",
}


def u16(b: bytes, o: int) -> int:
    return b[o] | (b[o + 1] << 8) if len(b) >= o + 2 else 0


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little") if len(b) >= o + 4 else 0


class Collector:
    def __init__(self, gdb: GdbClient):
        self.gdb = gdb
        self.f = open(OUTLOG, "w", encoding="utf-8")
        self.counts: dict[str, int] = {}
        self._seen: set = set()

    def log(self, s: str) -> None:
        self.f.write(s + "\n")
        self.f.flush()

    def hit(self, name: str) -> None:
        self.counts[name] = self.counts.get(name, 0) + 1

    def read(self, addr: int, n: int) -> bytes:
        try:
            return self.gdb.read_mem(addr, n)
        except Exception:
            return b""

    # ---- 关键：写 REG_KEYINPUT 注入按键 ----
    def set_keys(self, keys: list[str]) -> None:
        v = IDLE
        for k in keys:
            v &= ~KEY[k]
        self.gdb.cmd(f"M{KEYINPUT:x},2,{v:04x}".lower().replace("m", "M"))

    def tap(self, keys: list[str], hold_s: float = 0.12) -> None:
        """按下 → 跑一会儿 → 松开；用单步 continue 模拟时间流逝。"""
        self.set_keys(keys)
        self._spin(hold_s)
        self.set_keys([])
        self._spin(0.10)

    def _spin(self, seconds: float) -> None:
        """让模拟器跑 seconds 秒墙钟（用短 continue + 超时）。"""
        end = time.time() + seconds
        while time.time() < end:
            remain = max(0.05, end - time.time())
            try:
                self.gdb.cont(timeout=min(0.35, remain))
                self.gdb.cmd("?")           # 重同步
            except Exception:
                try:
                    self.gdb.cmd("?")
                except Exception:
                    return
            # 命中即处理（cont 返回表示停机）
            self._drain_once()

    def _drain_once(self) -> None:
        try:
            regs = self.gdb.read_regs()
        except Exception:
            return
        pc = regs.get("r15", 0) & ~1
        if pc in BREAKS:
            try:
                self.dispatch(pc, regs)
            except Exception as e:
                self.log(f"  !! handler error @0x{pc:08X}: {e}")

    # ---- handlers ----
    def dispatch(self, pc: int, regs: dict) -> None:
        if pc == 0x08003630:
            self.on_dgt(regs)
        elif pc == 0x08003708:
            self.on_gctn(regs)
        elif pc == 0x08003730:
            self.on_ggtp(regs)
        elif pc == 0x08002C68:
            self.on_itp(regs)

    def on_dgt(self, regs: dict) -> None:
        win = regs.get("r0", 0)
        lr = regs.get("r14", 0) & ~1
        wb = self.read(win, 0x24)
        if len(wb) < 0x22:
            return
        idx = u16(wb, 0x14)
        tptr = u32(wb, 0x10)
        cur = tptr + idx
        data = self.read(cur, 6)
        key = (win, idx, wb[0x0A], wb[0x0B])
        if key in self._seen:
            return
        self._seen.add(key)
        self.hit("DGT")
        a0 = self.tilemap_addr(win, wb, 0, 0)
        a1 = self.tilemap_addr(win, wb, 0, 1)
        t0, t1 = self.tnum(a0), self.tnum(a1)
        td = u32(wb, 0x20)
        self.log(
            f"\n[DGT] win=0x{win:08X} LR=0x{lr:08X}"
            f" textMode={wb[0x0A]} fontNum={wb[0x0B]} index={idx}"
        )
        self.log(
            f"  curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
            f" TILE_BASE=0x{u16(wb, 0x16):04X} TILE_OFF=0x{u16(wb, 0x18):04X}"
        )
        self.log(f"  当前字@0x{cur:08X} 字节={data.hex(' ')}")
        self.log(
            f"  官方砖号 TL=0x{t0:04X}(@{a0:08X}) BL=0x{t1:04X}(@{a1:08X})"
            f" Δ={t1 - t0 if (t0 >= 0 and t1 >= 0) else '?'}"
        )
        self.log(
            f"  tileData=0x{td:08X} → 落点 TL=0x{(td + 32 * t0) & 0xFFFFFFFF:08X}"
            f" BL=0x{(td + 32 * t1) & 0xFFFFFFFF:08X}"
        )

    def tilemap_addr(self, win: int, wb: bytes, xo: int, yo: int) -> int:
        if len(wb) < 0x20:
            return 0
        cx = (wb[0x1B] + wb[0x1A]) & 0xFF
        cy = (wb[0x1D] + wb[0x1C]) & 0xFF
        tpl = u32(wb, 0)
        tm = u32(self.read(tpl + 0x10, 4), 0) if tpl else 0
        row = (cy + 32 * yo) & 0xFFFF
        col = (cx + xo) & 0xFF
        return (tm + ((row << 5) + col) * 2) & 0xFFFFFFFF

    def tnum(self, addr: int) -> int:
        if not addr:
            return -1
        b = self.read(addr, 2)
        return u16(b, 0) if len(b) >= 2 else -1

    def on_gctn(self, regs: dict) -> None:
        win = regs.get("r0", 0)
        xo = regs.get("r1", 0) & 0xFF
        yo = regs.get("r2", 0) & 0xFF
        lr = regs.get("r14", 0) & ~1
        wb = self.read(win, 0x24)
        if len(wb) < 0x20:
            return
        key = (win, xo, yo, wb[0x1A], wb[0x1B], wb[0x1C], wb[0x1D])
        if key in self._seen:
            return
        self._seen.add(key)
        self.hit("GCTN")
        a = self.tilemap_addr(win, wb, xo, yo)
        self.log(
            f"\n[GCTN] win=0x{win:08X} xOff={xo} yOff={yo}"
            f" → tilemap项@0x{a:08X} 砖号=0x{self.tnum(a):04X} LR=0x{lr:08X}"
        )
        self.log(
            f"  curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
            f" TILE_BASE=0x{u16(wb, 0x16):04X} TILE_OFF=0x{u16(wb, 0x18):04X}"
            f" tileData=0x{u32(wb, 0x20):08X}"
        )

    def on_ggtp(self, regs: dict) -> None:
        f = regs.get("r0", 0) & 0xFF
        g = regs.get("r1", 0) & 0xFFFF
        key = ("ggtp", f, g)
        if key in self._seen:
            return
        self._seen.add(key)
        self.hit("GGTP")
        self.log(f"\n[GGTP] fontNum={f} glyph=0x{g:04X}")

    def on_itp(self, regs: dict) -> None:
        win = regs.get("r0", 0)
        tb = regs.get("r2", 0)
        cx = regs.get("r3", 0)
        wb = self.read(win, 0x24)
        self._seen.clear()          # 新串 → 清去重
        self.hit("ITP")
        self.log(f"\n[ITP] win=0x{win:08X} tile_base={tb} cur_x={cx}")
        if len(wb) >= 0x22:
            self.log(
                f"  textMode={wb[0x0A]} fontNum={wb[0x0B]}"
                f" TILE_BASE=0x{u16(wb, 0x16):04X} tileData=0x{u32(wb, 0x20):08X}"
            )

    def summary(self) -> None:
        self.log("\n===== SUMMARY =====")
        for k, v in sorted(self.counts.items()):
            self.log(f"  {k:8s} {v}")
        self.f.close()


def main() -> int:
    keep = 33236
    # 清理多余 mGBA
    o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mGBA.exe", "/FO", "CSV"],
                       capture_output=True, text=True, errors="replace")
    for m in re.finditer(r'"mGBA\.exe","(\d+)"', o.stdout):
        pid = int(m.group(1))
        if pid != keep:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    time.sleep(2)

    mgba = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT, creationflags=DETACHED,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[b1] mGBA pid={mgba.pid}", flush=True)
    time.sleep(9)

    gdb = GdbClient("127.0.0.1", 2345, timeout=6.0)
    gdb.connect()
    for addr in BREAKS:
        try:
            gdb.set_sw_break(addr)
        except Exception as e:
            print(f"[b1] 断点 0x{addr:08X} 失败: {e}", flush=True)
    print("[b1] 断点已挂:", ", ".join(f"0x{a:08X}" for a in BREAKS), flush=True)

    c = Collector(gdb)
    c.log(f"===== B1 (GDB-injected) {time.strftime('%F %T')} =====")
    c.log("断点: " + ", ".join(f"0x{a:08X}={n}" for a, n in BREAKS.items()))

    seq = [
        ("过标题", [["START"], ["A"], ["A"], ["START"]]),
        ("继续游戏", [["A"], ["A"], ["A"]]),
        ("走动", [["RIGHT"], ["DOWN"], ["LEFT"], ["UP"]]),
        ("交互", [["A"], ["A"]]),
        ("开菜单", [["START"]]),
        ("菜单内移动", [["DOWN"], ["DOWN"], ["A"]]),
        ("退出菜单", [["B"], ["B"]]),
    ]
    for label, taps in seq:
        print(f"[b1] {label}", flush=True)
        c.log(f"\n--- {label} ---")
        for t in taps:
            c.tap(t, 0.20)
        c._spin(0.6)

    # 再一次长走，制造更多文字
    for i in range(4):
        print(f"[b1] walk {i+1}", flush=True)
        for t in (["RIGHT"], ["RIGHT"], ["A"], ["DOWN"], ["LEFT"], ["A"]):
            c.tap(t, 0.22)
        c._spin(0.5)

    c.summary()
    print("[b1] 完成，日志:", OUTLOG, flush=True)
    gdb.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
