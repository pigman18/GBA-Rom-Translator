#!/usr/bin/env python3
"""B2 探针：加载 ROM + .sav，看标题界面是否有「继续」（存档被识别）。"""
from __future__ import annotations
import ctypes, ctypes.wintypes as wt, os, shutil, subprocess, sys, time
import zlib, struct

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated_new.gba")
SAV = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.sav")
OUTDIR = os.path.join(ROOT, ".tmp", "b2_shots")
os.makedirs(OUTDIR, exist_ok=True)

BP_RK = 0x0800043E
KEYS = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
        "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080}

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
PW_RENDERFULLCONTENT = 0x00000002


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def find_window(part):
    found = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        b = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, b, n + 1)
        if part.lower() in b.value.lower():
            found.append((hwnd, b.value))
        return True
    user32.EnumWindows(cb, 0)
    return found


def grab(hwnd, path):
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right, r.bottom
    if w <= 0 or h <= 0:
        return None
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    if not user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT):
        user32.PrintWindow(hwnd, mdc, 0)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w; bi.biHeight = -h; bi.biPlanes = 1; bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    raw = bytearray(); px = buf.raw
    for y in range(h):
        raw.append(0)
        for x in range(w):
            o = (y * w + x) * 4
            raw += bytes((px[o + 2], px[o + 1], px[o]))
    def ck(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    hdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ck(b"IHDR", hdr)
                           + ck(b"IDAT", zlib.compress(bytes(raw))) + ck(b"IEND", b""))
    return w, h


class H:
    def __init__(self, g):
        self.g = g; self.n = 0
    def shot(self, tag):
        wins = find_window("mGBA")
        if not wins:
            print("  找不到窗口", flush=True); return
        self.n += 1
        p = os.path.join(OUTDIR, f"p{self.n:02d}_{tag}.png")
        print("  shot", tag, grab(wins[0][0], p), flush=True)
    def _hit(self):
        try:
            self.g.set_sw_break(BP_RK)
            for _ in range(80):
                try: self.g.cont(timeout=0.15)
                except GdbError: pass
                try: regs = self.g.read_regs()
                except GdbError: continue
                if (regs.get("r15", 0) & ~1) == BP_RK:
                    return True
        except GdbError: pass
        finally:
            try: self.g.clear_sw_break(BP_RK)
            except GdbError: pass
        return False
    def kick(self, seq):
        for k in seq:
            if self._hit():
                self.g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                self.g.cmd("P2=00000000")
            try: self.g.cont(timeout=0.05)
            except GdbError: pass
    def tap(self, key, press=4, rel=4, settle=1.2):
        self.kick([key] * press + [0] * rel)
        t = time.time() + settle
        while time.time() < t:
            try: self.g.cont(timeout=0.2)
            except GdbError: pass


def main():
    # 把 sav 放到 ROM 同名位置
    sav_dst = os.path.splitext(ROM)[0] + ".sav"
    if os.path.exists(SAV):
        shutil.copyfile(SAV, sav_dst)
        print("copied sav ->", sav_dst, os.path.getsize(sav_dst), flush=True)
    fo = open(os.path.join(ROOT, ".tmp", "b2_probe.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print("mGBA pid", p.pid, flush=True)
    time.sleep(5)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    print("gdb connected", flush=True)
    h = H(g)
    h.shot("boot")
    h.tap(KEYS["START"], 6, 6, 2.5)
    h.shot("after_start")
    h.tap(KEYS["A"], 4, 4, 2.0)
    h.shot("after_a1")
    h.tap(KEYS["A"], 4, 4, 2.5)
    h.shot("after_a2")
    print("done", h.n, flush=True)
    g.close(); p.terminate()
    try: p.wait(timeout=5)
    except Exception: p.kill()
    fo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
