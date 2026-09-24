#!/usr/bin/env python3
"""B2 画面采集：启动 mGBA → 按键走到目标场景 → 截 mGBA 窗口 → 存 PNG。

设计要点（针对本项目已踩过的坑）：
  · **不读 GBA I/O 寄存器**（DISPCNT 偶发 0x-001、BG hofs 读垃圾值）⇒
    改为直接截 mGBA 的 Windows 窗口位图（PrintWindow），所见即所得。
  · 按键注入沿用 B1 修好的路径：ReadKeys 内 0x0800043E + P3/P2 双写，
    每拍「摘断点 → cont」。
  · mGBA 进程由本脚本持有 Popen（后台启动即死）。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
import zlib
import struct

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated_new.gba")
OUTDIR = os.path.join(ROOT, ".tmp", "b2_shots")
os.makedirs(OUTDIR, exist_ok=True)

BP_RK = 0x0800043E
KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080,
        "R": 0x0100, "L": 0x0200}

# ---- Windows 窗口截图 ----
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
PW_RENDERFULLCONTENT = 0x00000002


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def find_window(title_part: str):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if title_part.lower() in buf.value.lower():
            found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return found


def grab_window(hwnd, path):
    rect = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right, rect.bottom
    if w <= 0 or h <= 0:
        return None
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)
    if not ok:
        user32.PrintWindow(hwnd, mdc, 0)

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h          # 负数 = top-down
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)

    raw = bytearray()
    px = buf.raw
    for y in range(h):
        raw.append(0)
        for x in range(w):
            o = (y * w + x) * 4
            raw += bytes((px[o + 2], px[o + 1], px[o]))

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    hdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", hdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b""))
    open(path, "wb").write(data)
    return w, h


class Harness:
    def __init__(self, g):
        self.g = g
        self.shot_n = 0

    def shot(self, tag):
        wins = find_window("mGBA")
        if not wins:
            print(f"  [shot:{tag}] 找不到 mGBA 窗口", flush=True)
            return
        hwnd, title = wins[0]
        self.shot_n += 1
        p = os.path.join(OUTDIR, f"{self.shot_n:02d}_{tag}.png")
        r = grab_window(hwnd, p)
        print(f"  [shot:{tag}] {r} -> {os.path.basename(p)}  ({title})", flush=True)

    def _hit_rk(self):
        """跑到 ReadKeys 断点，返回是否命中。"""
        try:
            self.g.set_sw_break(BP_RK)
            for _ in range(60):
                try:
                    self.g.cont(timeout=0.15)
                except GdbError:
                    pass
                try:
                    regs = self.g.read_regs()
                except GdbError:
                    continue
                if (regs.get("r15", 0) & ~1) == BP_RK:
                    return True
        except GdbError:
            pass
        finally:
            try:
                self.g.clear_sw_break(BP_RK)
            except GdbError:
                pass
        return False

    def kick(self, seq):
        for k in seq:
            if self._hit_rk():
                self.g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                self.g.cmd("P2=00000000")
            try:
                self.g.cont(timeout=0.05)
            except GdbError:
                pass

    def tap(self, key, press=4, rel=4, settle=1.0):
        self.kick([key] * press + [0] * rel)
        t = time.time() + settle
        while time.time() < t:
            try:
                self.g.cont(timeout=0.2)
            except GdbError:
                pass


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "b2_run.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[b2] mGBA pid={p.pid}", flush=True)
    time.sleep(5)

    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    print("[b2] gdb 已连接", flush=True)
    h = Harness(g)

    A, Bk, START = KEYS["A"], KEYS["B"], KEYS["START"]
    DOWN, UP, RIGHT = KEYS["DOWN"], KEYS["UP"], KEYS["RIGHT"]

    def step(label, fn, shot=True):
        print(f"[b2] {label}", flush=True)
        fn()
        if shot:
            h.shot(label)

    step("00_boot", lambda: None, shot=True)
    step("01_start", lambda: h.tap(START, 6, 6, 2.5))
    step("02_titleskip", lambda: [h.tap(A, 4, 4, 1.5) for _ in range(3)])
    step("03_ingame", lambda: h.tap(A, 4, 4, 2.0))
    step("04_move", lambda: (h.kick([DOWN] * 25 + [0] * 3),
                             h.tap(A, 4, 4, 1.5)))
    step("05_dialog", lambda: [h.tap(A, 4, 4, 1.8) for _ in range(4)])
    step("06_menu", lambda: h.tap(START, 6, 6, 2.5))
    step("07_menu_down", lambda: [h.tap(DOWN, 5, 5, 1.2) for _ in range(3)])
    step("08_menu_enter", lambda: h.tap(A, 5, 5, 2.5))
    step("09_submenu", lambda: [h.tap(DOWN, 4, 4, 1.2) for _ in range(4)])
    step("10_submenu_enter", lambda: h.tap(A, 5, 5, 2.5))
    step("11_back", lambda: [h.tap(Bk, 4, 4, 1.5) for _ in range(2)])
    step("12_walk", lambda: (h.kick([DOWN] * 20 + [0] * 3),
                             h.kick([RIGHT] * 20 + [0] * 3),
                             h.tap(A, 4, 4, 1.5),
                             h.kick([UP] * 20 + [0] * 3)))

    print(f"[b2] 完成，截图 {h.shot_n} 张 -> {OUTDIR}", flush=True)
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
