#!/usr/bin/env python3
"""调研(153) 追查 0x0800076B（调用者）+ EWRAM 缓冲内容。

═══════════════════════════════════════════════════════════════════════════
【(152) 的稳定结果（只启动一次 mGBA，不闪屏）】
═══════════════════════════════════════════════════════════════════════════
20 次命中，全部一致：
    PC  = 0x08000DF4   ← 写 VRAM 的代码
    LR  = 0x0800076B   ← **调用者**
    R0  = 0x80000000   ← DMA 使能标志
    R3  = 0x020047F0 / 0x020053B0  ← **EWRAM 源缓冲（字形）**

⇒ 两条线索：
 A) 调用者 0x0800076B 是谁 —— 反汇编它就知道「谁在请求画字」
 B) EWRAM 0x020047F0 / 0x020053B0 里是什么 —— 那应该是字形数据本身，
    再追「谁写进这两个缓冲」就到 ROM 了

【本脚本】
 ① 反汇编 0x08000700..0x08000800（调用者）
 ② 反汇编 0x08000DC0..0x08000E30（写入者，已有片段）
 ③ 一次启动 mGBA，读 EWRAM 0x020047F0 / 0x020053B0 的内容
 ④ 判断是不是汉字字形

用法：python scripts/research/firered/153_caller_analysis.py
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

OUT = ROOT / "work" / "_probe" / "caller"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
BASE = 0x08000000
TMP = ROOT / "work" / "_probe" / "dis"
SW_HIDE = 0


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def dis(rom: bytes, addr: int, size: int = 0xC0) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "c.bin", TMP / "c.elf"
    b.write_bytes(rom[off:off + size])
    subprocess.run(["arm-none-eabi-objcopy", "-I", "binary", "-O",
                    "elf32-littlearm", "-B", "arm",
                    "--rename-section", ".data=.text", str(b), str(e)],
                   capture_output=True)
    r = subprocess.run(["arm-none-eabi-objdump", "-d",
                        "--adjust-vma=" + hex(addr), "-M", "force-thumb",
                        str(e)], capture_output=True, text=True)
    return [ln.rstrip() for ln in r.stdout.splitlines()
            if "file format" not in ln and "Disassembly" not in ln and ln.strip()]


def launch_hidden(cmd, cwd, env):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return subprocess.Popen(cmd, cwd=cwd, env=env,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            startupinfo=si)


def main() -> int:
    rom = ROM.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()

    print("=" * 78)
    print("① 反汇编调用者 LR=0x0800076B 附近")
    print("=" * 78)
    for ln in dis(rom, 0x08000700, 0xE0):
        print("  " + ln)

    print("\n" + "=" * 78)
    print("② 反汇编写入者 0x08000D80..0x08000E20")
    print("=" * 78)
    for ln in dis(rom, 0x08000D80, 0xA0):
        print("  " + ln)

    # ── ③ 启动一次，读 EWRAM 缓冲 ──────────────────────────────
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
    print("\n[启动 mGBA（隐藏，单次）]")
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

        # 等读档
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
        print("[已读档，读 EWRAM 缓冲]")

        for addr in (0x020047F0, 0x020053B0):
            try:
                blob = c.read_mem(addr, 128)
            except GdbError as e:
                print(f"  0x{addr:08X} 读失败: {e}")
                continue
            print(f"\n  ==== EWRAM 0x{addr:08X}（128 B）====")
            for k in range(0, 128, 32):
                print(f"    +0x{k:03X}: {blob[k:k+32].hex(' ')}")
            # 4bpp 画前 2 个 tile
            print(f"    按 4bpp 画前 2 tile：")
            for t in range(2):
                tb = blob[t * 32:(t + 1) * 32]
                if len(tb) < 32:
                    break
                for y in range(8):
                    row = tb[y * 4:(y + 1) * 4]
                    line = ""
                    for x in range(8):
                        b = row[x // 2]
                        v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                        line += "." if v == 0 else "#"
                    print(f"      {line}")
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
