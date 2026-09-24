#!/usr/bin/env python3
"""B2 精确导航采集：每步都截图，用于人工确认菜单层级。

流程：读档 → 主菜单(截图) → 逐项 DOWN 遍历(每步截图) → 进宝可梦列表 → 进信息页 → 翻页
"""
from __future__ import annotations
import ctypes, ctypes.wintypes as wt, os, shutil, subprocess, sys, time, zlib, struct

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient  # noqa

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated_new.gba")
SAV = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.sav")
OUTDIR = os.path.join(ROOT, ".tmp", "b2_nav")
os.makedirs(OUTDIR, exist_ok=True)

BP_RK = 0x0800043E
K = {"A": 0x0001, "B": 0x0002, "SELECT": 0x0004, "START": 0x0008,
     "RIGHT": 0x0010, "LEFT": 0x0020, "UP": 0x0040, "DOWN": 0x0080}

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
PW = 0x00000002


class BIH(ctypes.Structure):
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
    if not user32.PrintWindow(hwnd, mdc, PW):
        user32.PrintWindow(hwnd, mdc, 0)
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
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
    def _drain(self):
        try:
            s = self.g.sock
            s.settimeout(0.02)
            while True:
                try:
                    if not s.recv(4096):
                        break
                except Exception:
                    break
        except Exception:
            pass
    def shot(self, tag):
        wins = find_window("mGBA")
        if not wins:
            print("  !! 无窗口", flush=True); return
        self.n += 1
        p = os.path.join(OUTDIR, f"{self.n:02d}_{tag}.png")
        grab(wins[0][0], p)
        print(f"  [{self.n:02d}] {tag}", flush=True)
    def _hit(self):
        try:
            self.g.set_sw_break(BP_RK)
            for _ in range(80):
                try: self.g.cont(timeout=0.12)
                except Exception: pass
                try: regs = self.g.read_regs()
                except Exception:
                    self._drain(); continue
                if (regs.get("r15", 0) & ~1) == BP_RK:
                    return True
        except Exception:
            pass
        finally:
            try: self.g.clear_sw_break(BP_RK)
            except Exception: pass
            self._drain()
        return False
    def kick(self, seq):
        for k in seq:
            if self._hit():
                try:
                    self.g.cmd(f"P3={(k & 0xFFFFFFFF).to_bytes(4,'little').hex()}")
                    self.g.cmd("P2=00000000")
                except Exception:
                    pass
            try: self.g.cont(timeout=0.05)
            except Exception: pass
        self._drain()
    def tap(self, key, press=4, rel=4, settle=1.5):
        self.kick([key] * press + [0] * rel)
        t = time.time() + settle
        while time.time() < t:
            try: self.g.cont(timeout=0.2)
            except Exception: pass
    def hold(self, key, n, settle=0.8):
        self.kick([key] * n + [0] * 3)
        t = time.time() + settle
        while time.time() < t:
            try: self.g.cont(timeout=0.2)
            except Exception: pass


def main():
    shutil.copyfile(SAV, os.path.splitext(ROM)[0] + ".sav")
    fo = open(os.path.join(ROOT, ".tmp", "b2_nav.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print("pid", p.pid, flush=True)
    time.sleep(5)
    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()
    print("gdb ok", flush=True)
    h = H(g)
    A, Bk, ST = K["A"], K["B"], K["START"]
    D, U = K["DOWN"], K["UP"]

    h.tap(ST, 6, 6, 2.5)
    h.tap(A, 4, 4, 2.5)
    h.shot("01_loaded")
    time.sleep(2)

    # 打开主菜单，逐项截图
    h.tap(ST, 6, 6, 3.0)
    h.shot("02_menu_0")
    for i in range(7):
        h.tap(D, 5, 5, 1.5)
        h.shot(f"03_menu_d{i+1}")

    # 回到第一项再进（应该是最上面的项）
    for _ in range(7):
        h.tap(U, 5, 5, 1.2)
    h.shot("04_menu_top")
    h.tap(A, 5, 5, 3.5)
    h.shot("05_entered")
    time.sleep(1)
    h.tap(A, 5, 5, 3.5)
    h.shot("06_entered2")
    time.sleep(1)
    h.tap(A, 5, 5, 3.5)
    h.shot("07_entered3")
    time.sleep(1)
    h.kick([K["RIGHT"]] * 8 + [0] * 3); time.sleep(1.5)
    h.shot("08_right1")
    h.kick([K["RIGHT"]] * 8 + [0] * 3); time.sleep(1.5)
    h.shot("09_right2")
    h.kick([K["RIGHT"]] * 8 + [0] * 3); time.sleep(1.5)
    h.shot("10_right3")
    h.kick([K["RIGHT"]] * 8 + [0] * 3); time.sleep(1.5)
    h.shot("11_right4")
    h.kick([K["RIGHT"]] * 8 + [0] * 3); time.sleep(1.5)
    h.shot("12_right5")

    print("done", h.n, flush=True)
    g.close(); p.terminate()
    try: p.wait(timeout=5)
    except Exception: p.kill()
    fo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
