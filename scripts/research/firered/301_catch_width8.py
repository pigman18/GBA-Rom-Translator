"""调研(301) 精确抓小字：在「HP / 270/287」区域重绘时采样宽高。

═══ 300 的量测结果 ═══
队伍界面小字（HP、270/287）墨迹只有 **6 行高**，
而大字（喷火龙）是 12 行。⇒ 确实是两套字号。

═══ 295 为什么只采到一种 ═══
我采 0x03003DE0 得到 400 帧相同记录 —— 那段时间屏幕没重绘。

═══ 本次修正 ═══
① 进队伍界面
② **每帧读 0x03003E60（宽高）和 0x03003DE0（位图）**
③ 记录「宽高字节变化」的每一次（不要求位图也变）
④ 同时整个界面反复 UP/DOWN/A/B 触发各种重绘（名字、HP、菜单）
⑤ 统计出现过的所有 (宽,高) 组合

如果存在 8 宽字体，必然能在采样里出现。

用法：python scripts/research/firered/301_catch_width8.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "width8_301"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local K = { A = 1, B = 2, START = 8, UP = 64, DOWN = 128 }

local function setk(m) emu:setKeys(m) end
local function rd(a, l)
    local ok, b = pcall(function() return emu:readRange(a, l) end)
    if ok and b then return b end
    return nil
end
local function rd16(a)
    local ok, v = pcall(function() return emu:read16(a) end)
    if ok then return v end
    return 0
end
local function wr(nm, d)
    local f = assert(io.open(OUTP .. "/" .. nm, "wb"))
    f:write(d); f:close()
end

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local bn = 0
local lastwh = nil
local recs = {}
local nrec = 0
local keys = {}
local ki = 0
local tick = 0

local function dc_is(want, k)
    local dc = rd16(0x04000000)
    if dc == want then dc_n = dc_n + 1 else dc_n = 0 end
    return dc_n >= (k or 8)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    if phase == "await_title" then
        if dc_is(0x9F40, 10) then phase = "a1"; hold = 16; setk(K.A); return end
        if f > 8000 then DS_DONE(1, "no-title") end
        return
    end
    if phase == "a1" then phase = "await_menu"; return end
    if phase == "await_menu" then
        if dc_is(0x3140, 8) then phase = "up"; hold = 10; setk(K.UP); wait = 25; return end
        if f > 12000 then DS_DONE(1, "no-menu") end
        return
    end
    if phase == "up" then phase = "a2"; hold = 16; setk(K.A); wait = 80; return end
    if phase == "a2" then
        if dc_is(0x7F60, 20) then phase = "press_b"; bn = 0; return end
        if f > 16000 then DS_DONE(1, "no-recap") end
        return
    end
    if phase == "press_b" then
        bn = bn + 1
        if bn > 11 then phase = "open"; hold = 16; setk(K.START); wait = 90; return end
        setk(K.B); hold = 10; wait = 40
        return
    end
    if phase == "open" then phase = "down"; hold = 16; setk(K.DOWN); wait = 40; return end
    if phase == "down" then phase = "enter"; hold = 16; setk(K.A); wait = 220; return end
    if phase == "enter" then
        RL("[PARTY] dc=0x" .. string.format("%04X", rd16(0x04000000)))
        phase = "watch"
        tick = 0
        return
    end

    if phase == "watch" then
        -- 每帧看宽高
        local wh = rd(0x03003E60, 2)
        if wh and #wh == 2 and wh ~= lastwh then
            local buf = rd(0x03003DE0, 128) or string.rep("\0", 128)
            if nrec < 800 then
                nrec = nrec + 1
                recs[#recs + 1] = buf .. wh
            end
            lastwh = wh
        end

        tick = tick + 1
        -- 各种按键，逼出不同字号的重绘
        local r = tick % 60
        if r == 1 then setk(K.DOWN); hold = 4
        elseif r == 20 then setk(K.UP); hold = 4
        elseif r == 40 then setk(K.A); hold = 4
        elseif r == 55 then setk(K.B); hold = 4
        end

        if nrec >= 800 or f > 34000 then
            wr("widths.bin", table.concat(recs))
            RL("[REC] n=" .. nrec)
            DS_DONE(0, "done")
            return
        end
        return
    end

    if f > 40000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["widths.bin"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-1500:])
    p = OUT / "widths.bin"
    if p.exists():
        print(f"\n记录 {len(p.read_bytes()) // 130} 条")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
