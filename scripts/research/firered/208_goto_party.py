"""调研(208) 进入队伍界面并 dump，为导出小字做准备。

路线：读档 -> A 继续 -> START 开菜单 -> A 进队伍 -> dump

关键：全程截图，逐步确认位置，避免盲按。

单次启动纪律（沿用 152 的教训）：
 - STARTUPINFO + SW_HIDE，不起 150ms 轮询隐藏线程（避免闪屏）
 - 只启动一次
 - 不用 GDB（断点会冻住整个模拟器）

用法：python scripts/research/firered/208_goto_party.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party208"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")

local A, B, START = 1, 2, 8
local proved = false
local last_dc, stable = -1, 0
local pressed = {}
local hold = 0
local step = 0
local shot = 0
local wait = 0

local function setk(m) emu:setKeys(m) end
local function wr(name, data)
    local f = assert(io.open(OUTP .. "/" .. name, "wb"))
    f:write(data); f:close()
end
local function rd(a, n)
    local ok, b = pcall(function() return emu:readRange(a, n) end)
    if ok and b then return b end
    return nil
end
local function snap(tag)
    shot = shot + 1
    local n = string.format("%02d", shot)
    local v = rd(0x06000000, 0x18000)
    if v then wr("s" .. n .. "_" .. tag .. "_vram.bin", v) end
    local e = rd(0x02000000, 0x40000)
    if e then wr("s" .. n .. "_" .. tag .. "_ewram.bin", e) end
    local i = rd(0x03000000, 0x8000)
    if i then wr("s" .. n .. "_" .. tag .. "_iwram.bin", i) end
    emu:screenshot(OUTP .. "/s" .. n .. "_" .. tag .. ".png")
    RL("[SNAP] " .. n .. " " .. tag)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f

    if hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0) end
        return
    end
    if wait > 0 then
        wait = wait - 1
        return
    end

    -- 读档检测
    if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] f=" .. f)
            snap("menu")
            step = 1
            wait = 40
            return
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
        if f > 6000 then DS_DONE(1, "no-save") end
        return
    end

    -- 逐步推进
    if step == 1 then
        -- 继续游戏
        setk(A); hold = 10; step = 2; wait = 90
        RL("[STEP] continue: A")
    elseif step == 2 then
        snap("ingame")
        -- 开菜单
        setk(START); hold = 10; step = 3; wait = 90
        RL("[STEP] open menu: START")
    elseif step == 3 then
        snap("menu_open")
        -- 菜单第一项通常是队伍/宝可梦
        setk(A); hold = 10; step = 4; wait = 120
        RL("[STEP] enter first item: A")
    elseif step == 4 then
        snap("party_try1")
        -- 再等一会，让动画结束
        wait = 60; step = 5
    elseif step == 5 then
        snap("party_try1b")
        -- 尝试再按 A（可能进了查看界面）
        setk(B); hold = 10; step = 6; wait = 60
        RL("[STEP] B back")
    elseif step == 6 then
        snap("party_final")
        RL("[DONE-STEPS]")
        DS_DONE(0, "reached")
    end

    if f > 12000 then DS_DONE(1, "late") end
end))
'''

EXPECT = ["s01_menu.png"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=420,
                extra_env={"EMU_IDENT": SAVE_FR.read_bytes()[:8].hex()})
    print(r.report())
    print(r.log_text[-2500:])
    if not r.ok:
        return 1
    shots = sorted(OUT.glob("s*.png"))
    print(f"\n截图 {len(shots)} 张：")
    for s in shots:
        print(f"  {s.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
