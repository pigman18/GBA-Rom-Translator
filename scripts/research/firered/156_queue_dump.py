#!/usr/bin/env python3
"""调研(156) 读打印命令队列 —— 用修好的窗口模式，一次启动到位。

═══════════════════════════════════════════════════════════════════════════
【已完成的关键突破】
═══════════════════════════════════════════════════════════════════════════
 (153)(154) 已解出**打印入口**：

   0x08000C34  每帧执行的绘制主函数
   0x030000C8  命令队列基址（IWRAM）
   0x030000C9  当前索引（字节）

   每项 16 字节：
      +0x00 u32  源地址（ROM 或 EWRAM）
      +0x04 u32  目标地址（VRAM）
      +0x08 u16  长度
      +0x0A u16  类型（1..4，对应不同 DMA 控制字）
      +0x0C u32  额外参数

   类型3（0x08000D80 分支）= 16 位 DMA，即 (152) 抓到的 0x08000DF4

⇒ **只要读出队列，「源地址」就是字形数据在 ROM/EWRAM 的位置。**

【环境注意】
 mGBA 的 config.ini 曾有 fullscreen=1 导致全屏，已改回 0（480×360）。
 本脚本启动时再次确认窗口模式，并且**只在最后统一清理进程**。

用法：python scripts/research/firered/156_queue_dump.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "queue2"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
SW_HIDE = 0
CONFIG = ROOT / "tools" / "mgba_dev" / \
    "mGBA-build-2026-10-19-win64-9157-fd9dc5c2cbf234365068855851107e762fc6211b" / \
    "config.ini"


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def ensure_windowed() -> None:
    """启动前强制窗口模式，绝不留给全屏的机会。"""
    if not CONFIG.exists():
        return
    txt = CONFIG.read_text(encoding="utf-8", errors="replace")
    new = txt.replace("fullscreen=1", "fullscreen=0")
    if new != txt:
        CONFIG.write_text(new, encoding="utf-8")
        print("  （config.ini: fullscreen 1 → 0）")


def launch_hidden(cmd, cwd, env):
    """SW_HIDE 启动；**不起**轮询隐藏线程（那是闪屏来源）。"""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return subprocess.Popen(cmd, cwd=cwd, env=env,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            startupinfo=si)


def main() -> int:
    ensure_windowed()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))
    lua = OUT / "drive.lua"
    lua.write_text(r'''
local OUT = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A = 1
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
local logf = assert(io.open(OUT .. "/drive.log", "w"))
local function log(s) logf:write(s .. "\n"); logf:flush() end
local function setk(m) emu:setKeys(m) end
callbacks:add("frame", function()
    local f = emu:currentFrame()
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true; log("[PROVE] f=" .. f)
        end
    end
    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1
        else last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true; hold = 12; setk(A)
        end
        return
    end
    if f % 600 == 0 then log("[MENU] f=" .. f) end
end)
''', encoding="utf-8")

    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_IDENT"] = SAVE.read_bytes()[:8].hex()

    mgba = find_mgba()
    print("[1/4] 启动 mGBA（窗口模式 + 隐藏）")
    proc = launch_hidden([str(mgba), "--script", str(lua),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    try:
        c = GdbClient("127.0.0.1", 2345, timeout=15.0)
        c.connect()
        try:
            c.cont(timeout=0.3)
        except GdbError:
            pass

        logf = OUT / "drive.log"
        t0 = time.time()
        while time.time() - t0 < 60:
            if logf.exists() and "[PROVE]" in logf.read_text(
                    encoding="utf-8", errors="replace"):
                break
            try:
                c.cont(timeout=2.0)
            except GdbError:
                pass
        print("[2/4] 已读档")

        print("\n" + "=" * 78)
        print("① IWRAM 0x03000080..0x03000180（先看布局）")
        print("=" * 78)
        blk = c.read_mem(0x03000080, 0x100)
        for o in range(0, 0x100, 16):
            addr = 0x03000080 + o
            mark = " ← 0x030000C8" if addr <= 0x030000C8 < addr + 16 else ""
            print(f"  0x{addr:08X}: {blk[o:o+16].hex(' ')}{mark}")

        print("\n" + "=" * 78)
        print("② 按 16 字节项解析从 0x030000C8 起")
        print("=" * 78)
        raw = c.read_mem(0x030000C8, 16 * 64)
        print(f"  {'#':>3} {'源':>12} {'目标':>12} {'长度':>6} {'类型':>5} 说明")
        roms: list[int] = []
        n_ok = 0
        for k in range(64):
            it = raw[k * 16:(k + 1) * 16]
            if len(it) < 16:
                break
            src = int.from_bytes(it[0:4], "little")
            dst = int.from_bytes(it[4:8], "little")
            ln = int.from_bytes(it[8:10], "little")
            ty = int.from_bytes(it[10:12], "little")
            notes = []
            if 0x08000000 <= src < 0x0A000000:
                notes.append("源=ROM")
                roms.append(src)
            elif 0x02000000 <= src < 0x03000000:
                notes.append("源=EWRAM")
            elif 0x03000000 <= src < 0x03008000:
                notes.append("源=IWRAM")
            if 0x06000000 <= dst < 0x07000000:
                notes.append("目标=VRAM")
            if not notes:
                continue
            n_ok += 1
            print(f"  {k:>3} 0x{src:08X} 0x{dst:08X} {ln:>6} {ty:>5} "
                  f"{' '.join(notes)}")
        print(f"\n  有效项 {n_ok} / 64")

        if roms:
            print("\n" + "=" * 78)
            print(f"③ 源地址在 ROM 的项：{len(set(roms))} 个不同地址")
            print("=" * 78)
            seen = set()
            for src in roms:
                if src in seen:
                    continue
                seen.add(src)
                try:
                    blob = c.read_mem(src, 32)
                except GdbError:
                    continue
                islz = (blob[0] >> 4) == 1
                nib = set()
                for b in blob:
                    nib.add(b & 0xF)
                    nib.add(b >> 4)
                print(f"\n  0x{src:08X}"
                      f"{'  ★LZ77' if islz else ''}  nibble={sorted(nib)[:8]}")
                print(f"      {blob.hex(' ')}")
                if len(seen) >= 20:
                    break

        c.close()
    except GdbError as e:
        print(f"GDB 错误：{e}")
    finally:
        try:
            proc.terminate(); proc.wait(timeout=6)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
