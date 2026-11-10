#!/usr/bin/env python3
"""调研(163) 用 Lua 的 readRange 一次性 dump 全量内存（不用 GDB 读）。

═══════════════════════════════════════════════════════════════════════════
【(161)(162) 的教训】
═══════════════════════════════════════════════════════════════════════════
GDB 读内存这条路很脆：
 · target running 时读会失败（返回 S02 之类的停机包干扰解析）
 · 分块批量读时，偶尔一块失败就把整块填 0
 · Ctrl-C 中断后状态也不稳定

而 **Lua 的 emu:readRange 在 frame 回调里稳定可靠**——
前面 55/77/103 号脚本都成功 dump 过 256KB 的 EWRAM。

⇒ 本脚本**完全不用 GDB**，只用 Lua：
   ① 读档到中文菜单
   ② 在 frame 回调里 dump EWRAM/IWRAM/VRAM/PAL/OAM 到文件
   ③ 正常收尾（emu_run 的三层校验会保证它真的跑完）

之后全部离线分析，不再启模拟器。

用法：python scripts/research/firered/163_lua_dump.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "snap3"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
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
local done = false

local function setk(m) emu:setKeys(m) end
local function save(p, addr, len)
    local ok = pcall(function()
        local b = emu:readRange(addr, len)
        local f = assert(io.open(p, "wb"))
        f:write(b); f:close()
    end)
    return ok
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end

    -- 读档检测
    if (not proved) and frame > 200 and frame % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] f=" .. frame)
            -- 读档瞬间也存一份
            save(OUT .. "/ewram_at_prove.bin", 0x02000000, 0x40000)
        end
    end

    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1
        else last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true
            hold = 12
            setk(A)
        end
        if frame > 4000 then DS_DONE(1, "no-save") end
        return
    end

    -- 读档后等 200 帧让菜单稳定，然后 dump 一次就收工
    if (not done) and frame > 200 then
        done = true
        local n = 0
        if save(OUT .. "/ewram.bin",  0x02000000, 0x40000) then n = n + 1 end
        if save(OUT .. "/iwram.bin",  0x03000000, 0x8000)  then n = n + 1 end
        if save(OUT .. "/vram.bin",   0x06000000, 0x18000) then n = n + 1 end
        if save(OUT .. "/pal.bin",    0x05000000, 0x400)   then n = n + 1 end
        if save(OUT .. "/oam.bin",    0x07000000, 0x400)   then n = n + 1 end
        if save(OUT .. "/io.bin",     0x04000000, 0x100)   then n = n + 1 end
        emu:screenshot(OUT .. "/menu.png")
        RL(string.format("[DUMP] f=%d segs=%d", frame, n))
        DS_DONE(0, "dumped")
    end
    if frame > 4000 then DS_DONE(1, "late") end
end))
'''

EXPECT = ["ewram.bin", "iwram.bin", "vram.bin", "pal.bin", "oam.bin",
          "menu.png"]


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=600,
                rom=ROM_ZH, save=SAVE_FR, timeout=400,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print(r.log_text)
    if not r.ok:
        return 1

    print("\n产出大小：")
    for f in sorted(OUT.glob("*.bin")):
        data = f.read_bytes()
        nz = sum(1 for b in data if b)
        print(f"  {f.name:<22} {len(data):>8,} B  非零 {nz:>8,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
