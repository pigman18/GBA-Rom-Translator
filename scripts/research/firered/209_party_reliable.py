"""调研(209) 可靠地进入队伍界面。

═══ 208 的教训 ═══
208 假设「读档检测到 IDENT 就是进了游戏」，但实测那是**开场滚动文字**
（「冒险回顾」），A 只是在推进文字。真正的游戏画面还没到。

本脚本改进：
 ① 读档后**连续按 A 若干轮**，直到画面稳定（连续 N 帧 VRAM 不变）
 ② 用「画面稳定 + 有 OBJ（主角精灵）」作为进场判据
 ③ 进场后再 START 开菜单，逐项截图
 ④ 每一步都 dump，事后可用截图核对

判据（可靠）：
  · DISPCNT 的 OBJ 使能位（bit12）= 1  → 有精灵
  · VRAM 连续 30 帧不变              → 画面稳定

用法：python scripts/research/firered/209_party_reliable.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party209"

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
local a_count = 0
local stable_cnt = 0
local last_v = nil

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
    RL("[SNAP] " .. n .. " " .. tag)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    -- 阶段 0：等读档
    if phase == "boot" then
        if f > 200 and f % 30 == 0 and #IDENT == 8 then
            local ew = emu:readRange(0x02000000, 0x40000)
            if ew and ew:find(IDENT, 1, true) then
                proved = true
                phase = "press"
                RL("[PROVE] f=" .. f)
                snap("prove")
                hold = 10; setk(A)
                a_count = 1
                wait = 60
            end
        end
        if f > 6000 then DS_DONE(1, "no-save") end
        return
    end

    -- 阶段 1：连续按 A 直到画面稳定且有 OBJ
    if phase == "press" then
        local v = rd(0x06000000, 0x3000)
        local dc = emu:read16(0x04000000)
        local has_obj = (dc % 0x10000) >= 0x1000
        if v and last_v and v == last_v then
            stable_cnt = stable_cnt + 1
        else
            stable_cnt = 0
        end
        last_v = v

        if stable_cnt >= 30 and has_obj then
            RL("[INGAME] f=" .. f .. " dc=" .. string.format("0x%04X", dc)
               .. " a_count=" .. a_count)
            snap("ingame")
            phase = "menu"
            hold = 10; setk(START)
            wait = 80
            return
        end

        -- 每 80 帧按一次 A
        if a_count < 30 and f % 80 == 0 then
            a_count = a_count + 1
            setk(A); hold = 8
            RL("[A#] " .. a_count .. " f=" .. f)
        end
        if a_count >= 30 and stable_cnt < 30 then
            RL("[GIVEUP] a_count=30 stable=" .. stable_cnt)
            snap("giveup")
            DS_DONE(1, "no-ingame")
        end
        return
    end

    -- 阶段 2：菜单
    if phase == "menu" then
        snap("menu_start")
        RL("[STEP] menu opened, press A")
        hold = 10; setk(A)
        phase = "menu2"
        wait = 100
        return
    end

    if phase == "menu2" then
        snap("menu_a1")
        RL("[STEP] after A in menu, press A again")
        hold = 10; setk(A)
        phase = "menu3"
        wait = 120
        return
    end

    if phase == "menu3" then
        snap("menu_a2")
        RL("[DONE-STEPS]")
        DS_DONE(0, "done")
    end

    if f > 14000 then DS_DONE(1, "late") end
end))
'''

EXPECT = ["s01_prove.png"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=460,
                extra_env={"EMU_IDENT": SAVE_FR.read_bytes()[:8].hex()})
    print(r.report())
    print(r.log_text[-3000:])
    if not r.ok:
        return 1
    print(f"\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        print(f"  {s.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
