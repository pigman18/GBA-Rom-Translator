"""调研(216) 修正按键时长：火红需要更长的按键保持时间。

═══ 之前的问题 ═══
215 里 s02 和 s03 的 sha256 完全相同，说明**按 A 没有任何反应**。
hold = 10 帧 = 1/6 秒，可能太短（火红菜单确认需要更长的按键跨度）。

火红的按键检测通常是「帧级扫描」，但某些画面（存档选择）需要
按键保持 ~15-20 帧才被识别为一次完整按键。

本脚本：
 ① hold 改为 20 帧
 ② 每次按键后等 60 帧再判断
 ③ 全程每步截图，能看清哪一步没生效

用法：python scripts/research/firered/216_party_longpress.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party216"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")

local A, B, START = 1, 2, 8
local HOLDN = 20          -- 按键保持帧数
local hold, wait = 0, 0
local proved = false
local shot = 0
local phase = "boot"
local bc = 0
local last_dc, dcstable = -1, 0
local pressed = {}
local prev_sha = nil

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
            hold = HOLDN; setk(A)
            RL("[BOOT-A] f=" .. f)
        end
        if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
            local ew = emu:readRange(0x02000000, 0x40000)
            if ew and ew:find(IDENT, 1, true) then
                proved = true
                phase = "continue"
                RL("[PROVE] f=" .. f)
                snap("prove")
                return
            end
        end
        if f > 8000 then DS_DONE(1, "no-save") end
        return
    end

    -- 按 A 选「继续游戏」（长按）
    if phase == "continue" then
        hold = HOLDN; setk(A)
        RL("[PRESS] A long-press to continue")
        phase = "after_continue"
        wait = 70
        return
    end
    if phase == "after_continue" then
        snap("after_continue")
        phase = "mash_b"
        bc = 0
        return
    end

    -- 狂按 B 退出回顾（长按）
    if phase == "mash_b" then
        if bc >= 40 then
            RL("[B-DONE] bc=" .. bc)
            snap("after_b")
            phase = "settle"
            wait = 40
            return
        end
        bc = bc + 1
        setk(B); hold = 8
        return
    end

    if phase == "settle" then
        snap("settled")
        RL("[STABLE] -> START long-press")
        phase = "menu"
        hold = HOLDN; setk(START)
        wait = 90
        return
    end

    if phase == "menu" then
        snap("menu_open")
        RL("[STEP] menu -> A long")
        hold = HOLDN; setk(A)
        phase = "m2"; wait = 130
        return
    end
    if phase == "m2" then
        snap("m2")
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
    print("\n截图（含 sha 前 8 位，用于快速看哪几张相同）：")
    import hashlib
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<28} {h}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
