#!/usr/bin/env python3
"""调研(144) 测试 mGBA 能否同时用 --script（Lua 驱动）+ --gdb（抓执行）。

═══════════════════════════════════════════════════════════════════════════
【为什么需要这个】
═══════════════════════════════════════════════════════════════════════════
(141) 的 watchpoint 抓到了「ROM → EWRAM → VRAM」的链路，
但抓到的是**标题画面**的图形，不是中文菜单的字形。

要抓中文，必须让游戏先走到菜单。而：
 · Lua（--script）能按键
 · GDB（--gdb）能设断点/读内存
 问题是两者能否共存。

【测试】
 ① mGBA --script drive.lua --gdb rom.gba
 ② Lua 负责：读档进菜单，然后停在菜单（不再动作）
 ③ Python 侧：等 ~15 秒（Lua 已把游戏带到菜单）
 ④ 再连 GDB，设 watchpoint，抓「谁写字形」

 若 mGBA 在 --gdb 下不自动暂停（等客户端连接才暂停），这个方案就成立。

用法：python scripts/research/firered/144_script_plus_gdb.py
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "work" / "_probe" / "combo"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


# Lua：读档进菜单，停在菜单上不再动作
LUA = r'''
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
local logf = io.open(OUT .. "/drive.log", "w")
local function log(s) if logf then logf:write(s.."\n"); logf:flush() end end

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
        if dc == last_dc then stable = stable + 1 else
            last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true; hold = 12; setk(A) end
        return
    end
    -- 已读档：停在菜单不再动作（让 GDB 来抓）
    log("[AT-MENU] f=" .. f)
end)
'''

EXPECT = []


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))
    lua_path = OUT / "drive.lua"
    lua_path.write_text(LUA, encoding="utf-8")

    import os
    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_IDENT"] = SAVE.read_bytes()[:8].hex()

    mgba = find_mgba()
    print("① 启动 mGBA --script（Lua 驱动）+ --gdb")
    m = subprocess.Popen([str(mgba), "--script", str(lua_path),
                          "--gdb", str(rom_copy)],
                         cwd=str(OUT), env=env,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

    print("② 等 18 秒，看 Lua 能否把游戏带到菜单")
    time.sleep(18)
    dl = OUT / "drive.log"
    if dl.exists():
        print("  drive.log：")
        print("  " + dl.read_text(encoding="utf-8",
                                  errors="replace").replace("\n", "\n  "))
    else:
        print("  **没有 drive.log** ⇒ 可能 --gdb 让模拟器暂停了，Lua 没跑")

    print("\n③ 现在连 GDB，看能否读到状态")
    try:
        from util.debug_patcher import GdbClient, GdbError
        c = GdbClient("127.0.0.1", 2345, timeout=8.0)
        c.connect()
        io = c.read_mem(0x04000000, 0x10)
        dc = struct.unpack_from("<H", io, 0)[0]
        vc = struct.unpack_from("<H", io, 6)[0]
        print(f"  DISPCNT = 0x{dc:04X}   VCOUNT = 0x{vc:04X}")
        regs = c.cmd("g")
        hp = "".join(ch for ch in regs if ch in "0123456789abcdefABCDEF")[:68]
        if len(hp) >= 68:
            raw = bytes.fromhex(hp)
            pc = int.from_bytes(raw[60:64], "little")
            print(f"  PC = 0x{pc:08X}")
        c.close()
    except Exception as e:
        print(f"  GDB 连接/读取失败: {e}")

    print("\n④ 再等 3 秒看 Lua 是否还在跑")
    time.sleep(3)
    if dl.exists():
        txt = dl.read_text(encoding="utf-8", errors="replace")
        lines = [l for l in txt.splitlines() if l.strip()]
        print(f"  drive.log 行数 {len(lines)}，最后 3 行：")
        for l in lines[-3:]:
            print(f"    {l}")

    try:
        m.terminate(); m.wait(timeout=5)
    except Exception:
        m.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
