#!/usr/bin/env python3
"""调研(145) GDB 自己驱动游戏：直接写存档结构 + 跳过开场。

═══════════════════════════════════════════════════════════════════════════
【困境】
═══════════════════════════════════════════════════════════════════════════
 · mGBA --gdb 启动后**立刻暂停**，Lua 完全不跑（(144) 证实）
 · 所以只能用 GDB 驱动
 · 但 GDB 不能模拟按键（KEYINPUT 是只读硬件）

【绕开按键的三个办法】
 A) **直接写游戏的「主循环状态机」变量**，把游戏从标题跳到野外。
    需要知道是哪个变量 —— 未知。

 B) **用 GDB 的 `P` 包改 CPU 寄存器**，把 PC 直接跳到「读档函数」。
    需要知道读档函数地址 —— 可以从 gSaveBlock 相关函数找。

 C) ⭐ **最简单：让 GDB continue 很久，同时用 Windows API 给 mGBA 窗口发按键**。
    GDB 的 continue 是阻塞的，但可以放在**独立线程**里！
    主线程用 Windows 的 SendMessage/PostMessage 发 WM_KEYDOWN 到 mGBA 窗口。

    mGBA 的按键映射是键盘。用 PowerShell 的 SendKeys 或 win32 API 发键。

【本脚本采用 C】：
 ① 后台线程启动 GDB 连接 + 持续 continue
 ② 主线程用 PowerShell 的 SendKeys 给 mGBA 窗口发按键
 ③ 每发一轮就检查 GDB 是否命中了 watchpoint

⚠ 关键：mGBA 默认按键映射（需确认）：
    A = X 或 Z，B = Z 或 X，Start = Enter，方向 = 方向键
    常见默认：A=X, B=Z, L=A, R=S, Start=Enter, Select=Backspace

用法：python scripts/research/firered/145_gdb_plus_keyboard.py
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "gdbkbd"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def send_keys(hwnd: int, keys: str, hold_ms: int = 60):
    """给窗口发按键（用 PowerShell 的 SendKeys，需要先激活窗口）。"""
    ps = f'''
$sig = @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int n);
"@
$t = Add-Type -MemberDefinition $sig -Name W -Namespace N -PassThru
$h = [IntPtr]{hwnd}
$t::ShowWindow($h, 9) | Out-Null
$t::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 120
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{keys}")
'''
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=15)


def find_window() -> int:
    """找 mGBA 窗口句柄。"""
    ps = '''
Get-Process mGBA -ErrorAction SilentlyContinue |
  Where-Object { $_.MainWindowHandle -ne 0 } |
  Select-Object -First 1 -ExpandProperty MainWindowHandle
'''
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=15)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    mgba = find_mgba()
    print("① 启动 mGBA --gdb")
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(5)

    hwnd = find_window()
    print(f"② mGBA 窗口句柄 = {hwnd}")
    if not hwnd:
        print("  **找不到窗口，无法发按键**")
        m.terminate()
        return 1

    state = {"stop": False, "hits": [], "proved_pc": 0}

    def gdb_thread():
        try:
            c = GdbClient("127.0.0.1", 2345, timeout=10.0)
            c.connect()
            # 设 watchpoint 在 VRAM charBase（字形会被写进这里）
            for a in (0x06000000, 0x06004000, 0x06008000, 0x0600C000,
                      0x06010000):
                try:
                    c.cmd(f"Z2,{a:x},2")
                except GdbError:
                    pass
            print("  [gdb] watchpoint 已设")

            # 持续 continue，记录 watchpoint 命中
            while not state["stop"]:
                try:
                    why = c.cont(timeout=1.5)
                except GdbError:
                    continue
                if "watch" in str(why):
                    state["hits"].append(str(why))
                    print(f"  [gdb] {why}")
                    # 读 DMA3 源地址
                    try:
                        sad = struct.unpack("<I", c.read_mem(0x040000D4, 4))[0]
                        dad = struct.unpack("<I", c.read_mem(0x040000D8, 4))[0]
                        if 0x08000000 <= sad < 0x0A000000:
                            state["hits"].append(f"ROM→VRAM 0x{sad:08X}")
                            print(f"    ★ DMA 源 0x{sad:08X} → 0x{dad:08X}")
                    except GdbError:
                        pass
            c.close()
        except Exception as e:
            print(f"  [gdb] 异常: {e}")

    t = threading.Thread(target=gdb_thread, daemon=True)
    t.start()
    time.sleep(3)

    print("\n③ 用键盘驱动游戏（mGBA 默认 A=X / Start=Enter）")
    for i in range(12):
        time.sleep(2.0)
        send_keys(hwnd, "x")            # A
        time.sleep(1.0)
        send_keys(hwnd, "{ENTER}")      # Start
        print(f"  [轮{i}] 已发 A + Start")

    state["stop"] = True
    time.sleep(2)

    print("\n" + "=" * 78)
    print("④ 结果")
    print("=" * 78)
    print(f"  watchpoint 命中 {len(state['hits'])} 次")
    rom_hits = [h for h in state["hits"] if "ROM→VRAM" in str(h)]
    print(f"  其中「ROM → VRAM」{len(rom_hits)} 次：")
    for h in rom_hits[:15]:
        print(f"    {h}")

    try:
        m.terminate(); m.wait(timeout=5)
    except Exception:
        m.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
