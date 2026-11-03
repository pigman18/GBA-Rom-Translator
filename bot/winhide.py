"""bot/winhide.py — 隐藏 mGBA 窗口启动（headless 批处理）（从零重写 2026-10-06）

Windows 上要让 GUI 程序不弹窗，实测只有 STARTUPINFO + SW_HIDE 有效：
  - QT_QPA_PLATFORM=offscreen 会让 mGBA 崩（0xC0000142）
  - CREATE_NO_WINDOW 对 GUI 子系统程序无效
  - STARTUPINFO SW_HIDE 有效（窗口仍创建但不可见）

⚠ 另加一个极短 watchdog：SW_HIDE 在部分 Windows 版本偶发失效，
  5ms 后按 pid 枚举窗口再补一次 ShowWindow(SW_HIDE)。

⚠ 子进程 stdout/stderr 必须 DEVNULL：run.py 是靠 scene.log 判断完成的，
  不靠模拟器输出；管道还可能因沙箱限制报 EPERM。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    SW_HIDE = 0


def _hide_again(pid: int) -> None:
    """5ms 后按 pid 找窗口再隐藏一次。"""
    time.sleep(0.005)
    _hide_now(pid)


def _hide_now(pid: int) -> int:
    """把该 pid 的所有可见顶层窗口隐藏，返回隐藏了几个。

    mGBA 在 `--script` 之后会**再开一个脚本窗口**（标题"脚本"），它不是启动
    那一刻就存在的，所以只 hide 一次不够 —— 必须全程跟。
    """
    if not IS_WINDOWS:
        return 0
    n = 0
    try:
        hwnds: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _cb(hwnd, _):
            owner = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and _user32.IsWindowVisible(hwnd):
                hwnds.append(hwnd)
            return True

        _user32.EnumWindows(_cb, 0)
        for h in hwnds:
            _user32.ShowWindow(h, SW_HIDE)
            n += 1
    except Exception:
        pass
    return n


def _pid_alive(pid: int) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259            # STILL_ACTIVE
    except Exception:
        return False


def _keep_hidden(pid: int, interval: float = 0.15) -> None:
    """进程存活期间持续隐藏它新冒出来的窗口（脚本窗、OSD、模态框）。"""
    while _pid_alive(pid):
        _hide_now(pid)
        time.sleep(interval)


def popen_hidden(command, cwd=None, env=None):
    """启动子进程并隐藏其窗口。BOT_SHOW_WINDOW=1 时恢复可见（调试用）。"""
    show = os.environ.get("BOT_SHOW_WINDOW") == "1"

    if not IS_WINDOWS or show:
        return subprocess.Popen(command, cwd=cwd, env=env)

    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE

    proc = subprocess.Popen(
        command, cwd=cwd, env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=si,
    )
    threading.Thread(target=_hide_again, args=(proc.pid,), daemon=True).start()
    threading.Thread(target=_keep_hidden, args=(proc.pid,), daemon=True).start()
    return proc


def wait_hidden(proc, timeout: float | None = None) -> int:
    """等待进程结束；KeyboardInterrupt 时确保子进程被清理。"""
    try:
        return proc.wait(timeout=timeout)
    except KeyboardInterrupt:
        proc.kill()
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: winhide.py <command> [args...]")
        raise SystemExit(2)
    p = popen_hidden(sys.argv[1:])
    raise SystemExit(wait_hidden(p))
