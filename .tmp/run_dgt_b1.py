#!/usr/bin/env python3
"""B1 采集驱动器：mGBA(-g) + gdb_patcher(dgt-jp) + 自动按键走到有文字的界面。

设计：
  - mGBA 以 DETACHED 起（不会随本脚本退出而死）
  - patcher 以 PIPE 子进程起，本脚本持续喂输入、最后 kill 掉取 [SUMMARY]
  - 按键用 Windows SendInput / keybd_event 发给 mGBA 窗口（标题 "mGBA"）
  - 🔴 不探测 2345 端口（探测会抢占 stub 的单客户端槽位，导致握手超时）

按键映射（mGBA 默认）：
  Z = A，X = B，Enter = Start，Backspace = Select，方向键 = 十字键
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
PY = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
LOG = os.path.join(ROOT, "src", "util", "work", "POKEMON_RUBY_AXVJ00", "dgt_jp.log")

DETACHED = 0x00000008 | 0x00000200

# --- Win32 输入 ---
user32 = ctypes.windll.user32
VK = {
    "A": 0x5A, "B": 0x58, "START": 0x0D, "SELECT": 0x08,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
}
KEYEVENTF_KEYUP = 0x0002


def _find_mgba_window(exclude: set[int]) -> int:
    """找 mGBA 主窗口（标题里含 mGBA），排除用户自己那个 PID 的窗口。"""
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if "mGBA" in buf.value:
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value not in exclude:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def _mGBA_pids() -> list[int]:
    o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mGBA.exe", "/FO", "CSV"],
                       capture_output=True, text=True, errors="replace")
    return [int(m.group(1)) for m in re.finditer(r'"mGBA\.exe","(\d+)"', o.stdout)]


def _kill_extra_mgba(keep: int) -> None:
    for pid in _mGBA_pids():
        if pid != keep:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)


def press(hwnd: int, key: str, hold: float = 0.10, gap: float = 0.22) -> None:
    vk = VK[key]
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(hold)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(gap)


def hold(hwnd: int, key: str, dur: float) -> None:
    vk = VK[key]
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(dur)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.25)


def log(msg: str) -> None:
    print(f"[drv {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    drive_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    keep = 33236  # 用户的实例
    _kill_extra_mgba(keep)
    time.sleep(2)

    mgba = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT, creationflags=DETACHED,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log(f"mGBA pid={mgba.pid}")
    time.sleep(9)  # 等窗口起来；不探测端口

    if os.path.exists(LOG):
        os.remove(LOG)
    out_f = open(os.path.join(ROOT, ".tmp", "dgt_run.out"), "wb")
    pt = subprocess.Popen(
        [PY, os.path.join(ROOT, "src", "util", "gdb_patcher.py"), "log",
         "--preset", "dgt-jp", "--cont-timeout", "20",
         "--log", LOG],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out_f,
        stderr=subprocess.STDOUT,
    )
    log(f"patcher pid={pt.pid}")
    time.sleep(14)  # 等断点挂满

    hwnd = _find_mgba_window({keep})
    log(f"mGBA hwnd=0x{hwnd:X}")
    if not hwnd:
        log("找不到 mGBA 窗口 —— 用鼠标点一下模拟器窗口再跑")
        pt.kill()
        return 1
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(1)

    # 走到标题 → 进游戏 → 打开有文字的界面
    log("按键：过标题")
    for _ in range(3):
        press(hwnd, "START", hold=0.15, gap=1.2)
        press(hwnd, "A", hold=0.12, gap=0.7)

    log("按键：继续游戏（A 确认）")
    for _ in range(4):
        press(hwnd, "A", hold=0.12, gap=0.9)

    log("按键：走动 + 开门/开菜单（造文字）")
    for i in range(6):
        hold(hwnd, "RIGHT", 0.9)
        hold(hwnd, "DOWN", 0.9)
        hold(hwnd, "LEFT", 0.9)
        hold(hwnd, "UP", 0.9)
        press(hwnd, "A", hold=0.12, gap=1.4)   # 对话 / 开门
        log(f"  cycle {i + 1}")

    log("按键：开开始菜单（START）")
    press(hwnd, "START", hold=0.15, gap=2.0)
    press(hwnd, "A", hold=0.12, gap=1.5)

    # 剩余时间保持存活，让 patcher 持续采集
    deadline = time.time() + max(30, drive_seconds - 90)
    log(f"保持采集 {int(max(30, drive_seconds - 90))}s …")
    while time.time() < deadline:
        time.sleep(5)

    log("收尾：杀 patcher 取 SUMMARY")
    pt.kill()
    try:
        pt.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    out_f.close()
    log(f"日志行数 = {sum(1 for _ in open(LOG, encoding='utf-8', errors='replace')) if os.path.exists(LOG) else 0}")
    log("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
