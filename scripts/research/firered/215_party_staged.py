"""调研(215) 分阶段：先按 A 进入冒险回顾，确认后再按 B 退出，然后 START。

═══ 214 的错误 ═══
PROVE 触发时其实还在「继续游戏」菜单，我立刻狂按 B 把它取消了，回到标题。

正确顺序：
 ① 读档检测（还在菜单）
 ② **按 A** 选择「继续游戏」 → 进入冒险回顾
 ③ 等画面真的变了（确认进了回顾）
 ④ **狂按 B** 退出回顾
 ⑤ 画面稳定 → START 开菜单
 ⑥ A 进队伍

判据「进了回顾」：VRAM 变化 → 说明画面切换了。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party215"

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
local bc, ac = 0, 0
local last_dc, dcstable = -1, 0
local pressed = {}
local baseline = nil
local changed = 0
local lastv, stable = nil, 0

local function setk(m) emu:setKeys(m) end
local function rd(a, l)
    local ok, b = pcall(function() return emu:readRange(a, l) end)
    if ok and b then return b end
    return nil
end
local function wr(n, d)
    local f = assert(io.open(OUTP .. "/" .. n, "wb"))
    f:write(d); f:close()
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
                baseline = rd(0x06000000, 0x2000)
                phase = "enter_recap"
                RL("[PROVE] f=" .. f)
                snap("prove")
                return
            end
        end
        if f > 8000 then DS_DONE(1, "no-save") end
        return
    end

    -- 按 A 进入冒险回顾
    if phase == "enter_recap" then
        hold = 10; setk(A)
        phase = "wait_recap"
        wait = 60
        RL("[STEP] A to continue")
        return
    end

    -- 等画面真的变化（= 进了回顾）
    if phase == "wait_recap" then
        local v = rd(0x06000000, 0x2000)
        if v and baseline and v ~= baseline then
            changed = changed + 1
            if changed >= 8 then
                RL("[RECAP] detected f=" .. f)
                snap("recap_entered")
                phase = "mash_b"
                return
            end
        else
            changed = 0
        end
        ac = ac + 1
        if ac > 40 then
            -- 没进回顾，直接尝试下一步
            RL("[NO-RECAP] ac=" .. ac)
            snap("no_recap")
            phase = "settle"
            return
        end
        return
    end

    -- 狂按 B 退出回顾
    if phase == "mash_b" then
        if bc >= 60 then
            RL("[B-DONE] bc=" .. bc .. " f=" .. f)
            snap("after_b")
            phase = "settle"
            wait = 40
            return
        end
        bc = bc + 1
        setk(B); hold = 5
        return
    end

    -- 等稳定
    if phase == "settle" then
        local v = rd(0x06000000, 0x2000)
        if v and lastv and v == lastv then stable = stable + 1 else stable = 0 end
        lastv = v
        if stable >= 25 then
            snap("stable")
            RL("[STABLE] f=" .. f .. " -> START")
            phase = "menu"
            hold = 10; setk(START)
            wait = 90
            return
        end
        return
    end

    if phase == "menu" then
        snap("menu_open")
        RL("[STEP] menu -> A")
        hold = 10; setk(A)
        phase = "m2"; wait = 120
        return
    end
    if phase == "m2" then
        snap("m2")
        RL("[STEP] m2 -> A")
        hold = 10; setk(A)
        phase = "m3"; wait = 140
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
