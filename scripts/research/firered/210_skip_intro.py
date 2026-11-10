"""调研(210) 跳过开场回顾，进入队伍界面。

═══ 208/209 的教训 ═══
208：读档后一直在「冒险回顾」滚动文字，A 只推进文字，30 次不够。
209：读档检测加了 f%30 条件 + 6000 帧上限，反而更失败。

本脚本：
 ① 读档检测沿用 208（每 30 帧查一次 IDENT，上限 8000 帧）
 ② 读档后**每 40 帧按一次 A，最多 200 次**，直到画面稳定
 ③ 稳定性判据：VRAM 前 0x3000 连续 40 帧不变
 ④ 稳定后截图 + START 开菜单，再逐步 A

用法：python scripts/research/firered/210_skip_intro.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party210"

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
local shot = 0
local phase = "boot"
local acount = 0
local stable = 0
local lastv = nil
local last_dc, dcstable = -1, 0
local pressed = {}

local function setk(m) emu:setKeys(m) end
local function wr(n, d)
    local f = assert(io.open(OUTP .. "/" .. n, "wb"))
    f:write(d); f:close()
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
    RL("[SNAP] " .. n .. " " .. tag .. " f=" .. RUN.f)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    if phase == "boot" then
        -- 208 的关键：画面稳定就按 A（推进标题 → 读档界面）
        local dc = emu:read16(0x04000000)
        if dc == last_dc then dcstable = dcstable + 1
        else last_dc = dc; dcstable = 1 end
        if dcstable == 40 and not pressed[dc] then
            pressed[dc] = true
            hold = 12
            setk(A)
            RL("[BOOT-A] f=" .. f .. " dc=" .. string.format("0x%04X", dc))
        end

        if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
            local ew = emu:readRange(0x02000000, 0x40000)
            if ew and ew:find(IDENT, 1, true) then
                proved = true
                phase = "skip"
                RL("[PROVE] f=" .. f)
                snap("prove")
                return
            end
        end
        if f > 8000 then DS_DONE(1, "no-save") end
        return
    end

    -- 阶段 skip：连续按 A 跳过回顾，直到画面稳定
    if phase == "skip" then
        local v = rd(0x06000000, 0x3000)
        if v and lastv and v == lastv then
            stable = stable + 1
        else
            stable = 0
        end
        lastv = v

        if stable >= 40 and acount >= 3 then
            RL("[INGAME] f=" .. f .. " a=" .. acount .. " stable=" .. stable)
            snap("ingame")
            phase = "menu"
            hold = 10; setk(START)
            wait = 90
            return
        end

        if acount < 200 then
            acount = acount + 1
            setk(A); hold = 6
            if acount % 20 == 0 then
                RL("[A] " .. acount .. " f=" .. f .. " stable=" .. stable)
            end
        else
            snap("giveup")
            DS_DONE(1, "no-ingame")
        end
        return
    end

    if phase == "menu" then
        snap("menu_open")
        RL("[STEP] menu, press A")
        hold = 10; setk(A)
        phase = "m2"; wait = 110
        return
    end
    if phase == "m2" then
        snap("m2")
        RL("[STEP] m2, press A")
        hold = 10; setk(A)
        phase = "m3"; wait = 130
        return
    end
    if phase == "m3" then
        snap("m3")
        RL("[DONE]")
        DS_DONE(0, "done")
    end

    if f > 20000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_prove.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=520,
                extra_env={"EMU_IDENT": SAVE_FR.read_bytes()[:8].hex()})
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        print(f"  {s.name}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
