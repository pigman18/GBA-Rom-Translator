"""调研(213) 逐步截图，看清读档后的完整流程。

═══ 之前的问题 ═══
208-212 都是「盲按 N 次然后截图一次」，所以不知道中间发生了什么。
实测看到的是「继续游戏」菜单 → 一段滚动文字 → 战斗 → 标题画面。

本脚本：**每按一次键就截一张图**，形成完整时间线，一次看清流程。

按法：
  读档检测到之后，按 A 一次，等 50 帧，截图；
  重复 24 次。每次截图带序号，事后按序看。

用法：python scripts/research/firered/213_step_trace.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "steps213"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")

local A, B, START = 1, 2, 8
local hold, wait = 0, 0
local proved = false
local n = 0
local phase = "boot"
local last_dc, dcstable = -1, 0
local pressed = {}

local function setk(m) emu:setKeys(m) end
local function rd(a, l)
    local ok, b = pcall(function() return emu:readRange(a, l) end)
    if ok and b then return b end
    return nil
end
local function wr(name, d)
    local f = assert(io.open(OUTP .. "/" .. name, "wb"))
    f:write(d); f:close()
end
local function snap(tag)
    emu:screenshot(OUTP .. "/" .. tag .. ".png")
    RL("[SNAP] " .. tag .. " f=" .. RUN.f)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    if phase == "boot" then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then dcstable = dcstable + 1
        else last_dc = dc; dcstable = 1 end
        if dcstable == 40 and not pressed[dc] then
            pressed[dc] = true
            hold = 12; setk(A)
            RL("[BOOT-A] f=" .. f)
        end
        if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
            local ew = emu:readRange(0x02000000, 0x40000)
            if ew and ew:find(IDENT, 1, true) then
                proved = true
                phase = "trace"
                RL("[PROVE] f=" .. f)
                snap("t00_prove")
                wait = 40
                return
            end
        end
        if f > 8000 then DS_DONE(1, "no-save") end
        return
    end

    -- 每轮：截图 -> 按 A -> 等 50 帧
    if phase == "trace" then
        n = n + 1
        if n > 24 then
            RL("[DONE-TRACE] n=" .. n)
            DS_DONE(0, "traced")
            return
        end
        setk(A); hold = 8
        local tag = string.format("t%02d_afterA", n)
        RL("[PRESS] A #" .. n .. " f=" .. f)
        wait = 50
        -- 等完后截图（下一轮进来先截）
        phase = "shot"
        return
    end

    if phase == "shot" then
        snap(string.format("t%02d_afterA", n))
        phase = "trace"
        return
    end

    if f > 20000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["t00_prove.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560,
                extra_env={"EMU_IDENT": SAVE_FR.read_bytes()[:8].hex()})
    print(r.report())
    print(r.log_text[-2500:])
    print("\n截图：")
    for s in sorted(OUT.glob("t*.png")):
        print(f"  {s.name}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
