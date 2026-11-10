"""调研(212) 读档后先脱离战斗，再进队伍。

═══ 210 的观察 ═══
读档后按 A 会一直推进**战斗**（火焰鸟 vs 哈克龙），200 次也没结束。

对策：
 ① 读档后**不按 A**，先观察：等 N 帧看画面是否自己变化（战斗动画自动走）
 ② 若稳定，按 B（逃跑/退出）
 ③ 反复 B 直到画面变成地图（有主角、有地图 tileset）
 ④ 再按 START 开菜单 → 进队伍

判据「已回到地图」：
  - 出现主角精灵（OBJ）
  - VRAM 里没有战斗血条（可以用画面稳定性 + B 的响应判断）

简化：直接按 B 最多 100 次，每次间隔 40 帧，然后截图看。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party212"

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
local bcount = 0
local acount = 0
local lastv, stable = nil, 0
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
                phase = "exit"
                RL("[PROVE] f=" .. f)
                snap("prove")
                return
            end
        end
        if f > 8000 then DS_DONE(1, "no-save") end
        return
    end

    -- 阶段 exit：按 B 尝试脱离战斗/菜单，每 40 帧 B 一次，最多 60 次
    if phase == "exit" then
        if bcount >= 60 then
            snap("exit_done")
            RL("[EXIT-DONE] b=" .. bcount)
            phase = "check"
            wait = 60
            return
        end
        bcount = bcount + 1
        setk(B); hold = 6
        if bcount % 10 == 0 then
            RL("[B] " .. bcount .. " f=" .. f)
        end
        return
    end

    if phase == "check" then
        snap("after_b")
        -- 再按 START 试开菜单
        RL("[STEP] press START")
        hold = 10; setk(START)
        phase = "menu"; wait = 100
        return
    end

    if phase == "menu" then
        snap("menu_open")
        RL("[STEP] menu, press A")
        hold = 10; setk(A)
        phase = "m2"; wait = 120
        return
    end
    if phase == "m2" then
        snap("m2")
        RL("[STEP] m2, press A")
        hold = 10; setk(A)
        phase = "m3"; wait = 140
        return
    end
    if phase == "m3" then
        snap("m3")
        RL("[DONE]")
        DS_DONE(0, "done")
    end

    if f > 26000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_prove.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560,
                extra_env={"EMU_IDENT": SAVE_FR.read_bytes()[:8].hex()})
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        print(f"  {s.name}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
