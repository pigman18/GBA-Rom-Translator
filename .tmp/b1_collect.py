#!/usr/bin/env python3
"""B1 正式采集器 —— Wokann DrawGlyphTiles+2 方案开工前取证（2026-09-20）。

已破的阻塞（见 .tmp/t_*.py 实验）：
  1. mGBA 起不来 → 脚本全程持有 Popen 引用（不 detached、不后台化）
  2. 按键注入 → REG_KEYINPUT 是**只读**硬件寄存器，写它无效（t_semantics2 实证）
     ⇒ 改在 ReadKeys(0x0800042C) 的 `strh r3,[r2,#0x28]`(0x0800047E) 下断点，
       命中时用 GDB 'P' 包改写 r3 ⇒ 按键走**游戏原生路径**（含 L=A 重映射/key repeat）
  3. gMain 地址 → 反汇编实证 = **0x030016E0**（pokeruby_jp.sym 写的 0x03001770 是错的！）
     字段：+0x28 heldKeysRaw / +0x2A newKeysRaw / +0x2C heldKeys / +0x2E newKeys
           +0x30 newAndRepeatedKeys / +0x32 keyRepeatCounter / +0x36 watchedKeysMask

采集三问：
  (a) DGT 钩内 win[0x10]+win[0x14] 是否 = 当前正在画的字
  (b) 官方砖号（*(u16*)GetCursorTileNum(win,0,yOff)）是否逐字 +1、无相位
  (c) tm0/tm1/tm2 三路是否都过 DrawGlyphTiles（钩点完备性）
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

BP_DGT = 0x08003630    # DrawGlyphTiles
BP_GCTN = 0x08003708   # GetCursorTileNum
BP_GGTP = 0x08003730   # GetGlyphTilePointers
BP_RK = 0x0800047E     # ReadKeys: strh r3,[r2,#0x28]  ← 按键注入点

GMAIN = 0x030016E0
GMAIN_HELD = GMAIN + 0x2C
GMAIN_NEW = GMAIN + 0x2E

REG_NUM = {"r0": 0, "r1": 1, "r2": 2, "r3": 3, "r4": 4, "r5": 5, "r6": 6,
           "r7": 7, "r8": 8, "r9": 9, "r10": 10, "r11": 11, "r12": 12,
           "sp": 13, "lr": 14, "pc": 15}

KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}

# 调用点归属（BL 落回 DGT 的 4 处，已静态实证）
CALLSITES = {
    0x08002AA6: "InitWindowTileData/tm1图集",
    0x08002B16: "InitWindowTileData族",
    0x080033A2: "tm2(glyphSpace2bpp)",
    0x08003542: "tm0(linear)",
}


def u16(b: bytes, o: int) -> int:
    return b[o] | (b[o + 1] << 8) if len(b) >= o + 2 else -1


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little") if len(b) >= o + 4 else 0


class B1:
    def __init__(self, g: GdbClient):
        self.g = g
        self.f = open(OUTLOG, "w", encoding="utf-8")
        self.seen: set = set()
        self.cnt: collections.Counter = collections.Counter()
        self.callers: collections.Counter = collections.Counter()
        self.modes: collections.Counter = collections.Counter()

    def log(self, s: str = "") -> None:
        self.f.write(s + "\n")
        self.f.flush()

    def poke(self, name: str, val: int) -> None:
        n = REG_NUM[name]
        self.g.cmd(f"P{n:x}={(val & 0xFFFFFFFF).to_bytes(4,'little').hex()}")

    # ---------- 断点处理 ----------
    def on_readkeys(self, regs: dict, key_state: list) -> None:
        """命中 ReadKeys 的 strh 前：把 r3 换成脚本键值。"""
        want = key_state[0]
        real = regs.get("r3", 0)
        self.cnt["RK"] += 1
        if want is not None and want != real:
            try:
                self.poke("r3", want)
                self.cnt["RK_injected"] += 1
            except GdbError:
                pass

    def on_dgt(self, regs: dict) -> None:
        win = regs.get("r0", 0)
        lr = regs.get("r14", 0) & ~1
        wb = self.g.read_mem(win, 0x24)
        if len(wb) < 0x24:
            return
        idx = u16(wb, 0x14)
        tptr = u32(wb, 0x10)
        textm = wb[0x0A]
        font = wb[0x0B]
        self.cnt["DGT"] += 1
        self.callers[f"0x{lr:08X}"] += 1
        self.modes[f"tm{textm}/font{font}"] += 1

        # 当前字（判据 a）
        cur_addr = (tptr + idx) & 0xFFFFFFFF
        raw = self.g.read_mem(cur_addr, 8)
        # 去重：同一 (win, index, tm, font) 只记第一次
        k = (win, idx, textm, font)
        if k in self.seen:
            return
        self.seen.add(k)

        tdbase = u32(wb, 0x20)
        tb = u16(wb, 0x16)
        toff = u16(wb, 0x18)
        cx, ctx_ = wb[0x1A], wb[0x1B]
        cy, cty = wb[0x1C], wb[0x1D]
        # 官方砖号（判据 b）
        t0, a0 = self.cur_tile(win, wb, 0, 0)
        t1, a1 = self.cur_tile(win, wb, 0, 1)
        call = CALLSITES.get(lr, f"LR=0x{lr:08X}")

        self.log(f"\n[DGT] win=0x{win:08X} LR=0x{lr:08X} [{call}]")
        self.log(f"  tm={textm} font={font} index={idx}"
                 f" TILE_BASE=0x{tb:04X} TILE_OFF=0x{toff:04X}"
                 f" tileData=0x{tdbase:08X}")
        self.log(f"  字形: lead=0x{wb[0x0E] if len(wb)>0x0E else -1:02X}"
                 f" trail=0x{wb[0x0F] if len(wb)>0x0F else -1:02X}"
                 f"  → (lead<<8|trail)=0x{((wb[0x0E]<<8)|wb[0x0F]) if len(wb)>0x0F else 0:04X}")
        self.log(f"  CUR: (TX={ctx_} + X={cx})=cx{wb[0x1B]+wb[0x1A]}"
                 f" (TY={cty} + Y={cy})=cy{wb[0x1D]+wb[0x1C]}")
        self.log(f"  当前字地址=0x{cur_addr:08X} 字节={raw.hex(' ')}"
                 f"  ↳ '{self._show(raw)}'")
        self.log(f"  官方砖号 TL=0x{t0:04X}@{a0:08X} BL=0x{t1:04X}@{a1:08X}"
                 f" ΔTLBL={t1 - t0 if t0 >= 0 and t1 >= 0 else '?'}"
                 f" 落点TL=0x{(tdbase + 32 * t0) & 0xFFFFFFFF:08X}"
                 f" BL=0x{(tdbase + 32 * t1) & 0xFFFFFFFF:08X}")

    def cur_tile(self, win: int, wb: bytes, xo: int, yo: int):
        """复刻 GetCursorTileNum 公式，返回 (砖号, tilemap项地址)。"""
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
        if raw[0] == 0xF9:
            return f"<双字节 0xF9{raw[1]:02X}{raw[2]:02X}>"
        if raw[0] == 0xF8:
            return f"<控制 0xF8{raw[1]:02X}>"
        if raw[0] == 0xFC:
            return f"<控制 0xFC{raw[1]:02X}{raw[2]:02X}>"
        if raw[0] == 0xFF:
            return "<串结束>"
        return f"byte 0x{raw[0]:02X}"

    def summary(self) -> None:
        self.log("\n===== SUMMARY =====")
        for k, v in sorted(self.cnt.items()):
            self.log(f"  {k:16s} {v}")
        self.log("  --- DGT 调用点分布 ---")
        for k, v in self.callers.most_common():
            self.log(f"    {k}  {CALLSITES.get(int(k, 16), '')}  ×{v}")
        self.log("  --- textMode/font 分布 ---")
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
    for a, nm in ((BP_DGT, "DGT"), (BP_GCTN, "GCTN"), (BP_GGTP, "GGTP"),
                  (BP_RK, "RK")):
        g.set_sw_break(a)
    print("[b1] 断点已挂: DGT/GCTN/GGTP/RK", flush=True)

    b = B1(g)
    b.log(f"===== B1 正式采集 @ {time.strftime('%F %T')} =====")
    b.log(f"gMain=0x{GMAIN:08X}(反汇编实证) 注入点=ReadKeys 0x{BP_RK:08X}")

    # 按键脚本：[按键值]；None = 不改（放行真实键）
    A, B_, START, DOWN, UP, RIGHT, LEFT = (0x0001, 0x0002, 0x0008, 0x0080,
                                           0x0040, 0x0010, 0x0020)
    # 每段: (标签, 持续秒, 按键拍序列)
    PLAN = [
        ("过标题", 5.0, [0] * 30 + [START] * 8 + [0] * 40),
        ("标题→继续", 5.0, [0] * 20 + [START] * 8 + [0] * 20 + [A] * 8 + [0] * 40),
        ("进游戏", 6.0, [0] * 10 + ([A] * 6 + [0] * 20) * 2),
        ("走动", 8.0, [0] * 10 + ([RIGHT] * 12 + [0] * 6) * 2
                     + ([DOWN] * 12 + [0] * 6) * 2),
        ("开菜单", 8.0, [0] * 10 + [START] * 8 + [0] * 30
                       + [DOWN] * 8 + [0] * 20 + [A] * 8 + [0] * 30),
        ("对话/交互", 10.0, [0] * 10 + ([A] * 6 + [0] * 24) * 3),
        ("菜单遍历", 10.0, [0] * 10 + [START] * 8 + [0] * 20
                         + ([DOWN] * 6 + [0] * 14) * 4 + [A] * 8 + [0] * 30),
    ]

    key_state = [None]

    def spin(seconds: float, want_keys: list) -> None:
        """跑 seconds 秒；每命中一次 ReadKeys 消费一个 key 拍。"""
        idx = 0
        end = time.time() + seconds
        while time.time() < end:
            key_state[0] = want_keys[idx % len(want_keys)] if want_keys else None
            idx += 1
            try:
                g.cont(timeout=0.18)
            except GdbError:
                pass
            # cont 停机（或超时）后读 pc 分派
            for _ in range(6):   # 连续处理多个连续命中
                try:
                    regs = g.read_regs()
                except GdbError:
                    break
                pc = regs.get("r15", 0) & ~1
                if pc == BP_RK:
                    b.on_readkeys(regs, key_state)
                    break
                if pc == BP_DGT:
                    try:
                        b.on_dgt(regs)
                    except GdbError:
                        pass
                    break
                if pc == BP_GCTN:
                    b.cnt["GCTN"] += 1
                    break
                if pc == BP_GGTP:
                    b.cnt["GGTP"] += 1
                    break
                break   # 非断点，交给下一次 cont
            if time.time() >= end:
                break

    for label, secs, keys in PLAN:
        print(f"[b1] {label} ({secs}s)", flush=True)
        b.log(f"\n\n########## {label} ##########")
        spin(secs, keys)

    # 收尾：多走几轮制造画字
    for i in range(3):
        print(f"[b1] 补走 {i+1}", flush=True)
        b.log(f"\n\n########## 补走 {i+1} ##########")
        spin(8.0, [0] * 10 + ([A] * 6 + [0] * 20 + [DOWN] * 6 + [0] * 14) * 3)

    b.summary()
    print(f"[b1] 完成。日志: {OUTLOG}", flush=True)
    try:
        print(f"[b1] gMain.heldKeys=0x{int.from_bytes(g.read_mem(GMAIN_HELD,2),'little'):04X}"
              f" DISPCNT=0x{int.from_bytes(g.read_mem(0x04000000,2),'little'):04X}", flush=True)
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
