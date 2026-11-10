#!/usr/bin/env python3
"""调研(146) 修正：watchpoint 命中时读 **CPU 寄存器**（r0-r3），不是 DMA 寄存器。

═══════════════════════════════════════════════════════════════════════════
【(145) 的问题】
═══════════════════════════════════════════════════════════════════════════
21 次 watchpoint 命中，但「ROM→VRAM」0 次。
原因：我在命中时读 0x040000D4（DMA3SAD），但 DMA 完成时它可能已清零，
或者这次不是走 DMA3。

(138) 的成功经验：命中时读 **CPU 寄存器 r3**，那里是源地址：
    r3=0x0200453C（EWRAM）  r2=0x06000000（VRAM 目标）

⇒ 正确做法：命中时 `g` 读寄存器，看 r0-r3。

【本脚本】
 ① 同时用 GDB（watchpoint）+ 键盘驱动（把游戏带到中文菜单）
 ② 命中时读 **寄存器**，记录所有 r0-r7 里的 ROM 地址
 ③ 统计哪些 ROM 地址被反复引用（那就是字形源的候选）
 ④ 对候选地址试 LZ77 解压

用法：python scripts/research/firered/146_regs_on_hit.py
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

OUT = ROOT / "work" / "_probe" / "regshit"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def send_keys(hwnd: int, keys: str):
    ps = f'''
$sig = @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int n);
"@
$t = Add-Type -MemberDefinition $sig -Name W -Namespace N -PassThru
$h = [IntPtr]{hwnd}
$t::ShowWindow($h, 9) | Out-Null
$t::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 100
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{keys}")
'''
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=15)


def find_window() -> int:
    ps = ('Get-Process mGBA -ErrorAction SilentlyContinue | '
          'Where-Object { $_.MainWindowHandle -ne 0 } | '
          'Select-Object -First 1 -ExpandProperty MainWindowHandle')
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
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(5)
    hwnd = find_window()
    print(f"① mGBA 窗口 = {hwnd}")

    state = {"stop": False, "hits": []}

    def gdb_thread():
        try:
            c = GdbClient("127.0.0.1", 2345, timeout=10.0)
            c.connect()
            for a in (0x06000000, 0x06004000, 0x06008000, 0x0600C000):
                try:
                    c.cmd(f"Z2,{a:x},2")
                except GdbError:
                    pass
            print("  [gdb] watchpoint 已设（4 个 VRAM 地址）")

            while not state["stop"]:
                try:
                    why = c.cont(timeout=1.5)
                except GdbError:
                    continue
                if "watch" not in str(why):
                    continue
                # ★ 命中：读 CPU 寄存器
                try:
                    regs = c.cmd("g")
                except GdbError:
                    continue
                hp = "".join(ch for ch in regs
                             if ch in "0123456789abcdefABCDEF")[:68]
                if len(hp) < 68:
                    continue
                try:
                    raw = bytes.fromhex(hp)
                except ValueError:
                    continue
                vals = [int.from_bytes(raw[k * 4:(k + 1) * 4], "little")
                        for k in range(16)]
                pc = vals[15]
                lr = vals[14]
                rom_ptrs = [v for v in vals[:8]
                            if 0x08000000 <= v < 0x0A000000]
                rec = {
                    "why": str(why),
                    "pc": pc, "lr": lr,
                    "r": vals[:8],
                    "rom": rom_ptrs,
                }
                state["hits"].append(rec)
                print(f"  [gdb] {why}")
                print(f"        PC=0x{pc:08X} LR=0x{lr:08X}")
                print(f"        r=[{', '.join(f'0x{v:08X}' for v in vals[:5])}]")
                if rom_ptrs:
                    print(f"        ★ ROM: {[f'0x{v:08X}' for v in rom_ptrs]}")
            c.close()
        except Exception as e:
            print(f"  [gdb] 异常: {e}")

    t = threading.Thread(target=gdb_thread, daemon=True)
    t.start()
    time.sleep(3)

    print("\n② 键盘驱动（A + Start 交替）")
    for i in range(15):
        send_keys(hwnd, "x")
        time.sleep(0.8)
        send_keys(hwnd, "{ENTER}")
        time.sleep(1.2)
        print(f"  [轮{i}]")

    state["stop"] = True
    time.sleep(2)

    print("\n" + "=" * 78)
    print("③ 汇总")
    print("=" * 78)
    print(f"  watchpoint 命中 {len(state['hits'])} 次")
    allrom = []
    for h in state["hits"]:
        allrom.extend(h["rom"])
    from collections import Counter
    c2 = Counter(allrom)
    print(f"  寄存器里出现的 ROM 地址（去重 {len(c2)} 个）：")
    for a, n in c2.most_common(20):
        print(f"    0x{a:08X}  ×{n}")
    # PC 分布
    pc = Counter(h["pc"] for h in state["hits"])
    print(f"\n  命中时的 PC（写 VRAM 的代码）：")
    for p, n in pc.most_common(10):
        print(f"    0x{p:08X}  ×{n}")

    try:
        m.terminate(); m.wait(timeout=5)
    except Exception:
        m.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
