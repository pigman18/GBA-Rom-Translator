"""调研(231) 等回顾过场真正开始（DISPCNT==0x7F60 稳定）后再按 B 跳过。

═══ 前面所有失败的共同根因 ═══
按键按在了**错误的时间点**：
  · 219/222：在白屏/加载中按 B → 把「继续游戏」确认取消 → 退回标题
  · 229：把自动播放的回顾当成"卡住"，按 START → 回顾从头播
  · 230：按 A → 只是翻页

火红读档后的真实时序：
  DISPCNT 0x3140 「继续游戏」菜单
    --A-->  加载（黑屏，短暂）
    --进游戏--> DISPCNT 0x7F60，开始播放「冒险回顾」过场
    --B-->  跳过回顾（⚠ 必须等 0x7F60 稳定后再按，早按会取消读档）
    -->  野外，可操作
    --START--> 系统菜单
    --宝可梦--> 队伍

本脚本严格按这个时序，每步都等 DISPCNT 到位。

用法：python scripts/research/firered/231_skip_recap_right.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party231"

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

local shotn = 0
local function do_shot(name, dump)
    shotn = shotn + 1
    local i = string.format("%02d", shotn)
    local dc = rd16(0x04000000)
    emu:screenshot(OUTP .. "/s" .. i .. "_" .. name .. ".png")
    if dump then
        for _, sp in ipairs({
            { "vram", 0x06000000, 0x18000 },
            { "ewram", 0x02000000, 0x40000 },
            { "iwram", 0x03000000, 0x8000 },
            { "pal", 0x05000000, 0x400 },
        }) do
            local d = rd(sp[2], sp[3])
            if d then wr("s" .. i .. "_" .. name .. "_" .. sp[1] .. ".bin", d) end
        end
    end
    RL(string.format("[SHOT] %02d %-18s dc=0x%04X f=%d", shotn, name, dc, RUN.f))
end

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local stepn = 0
local bn = 0

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
        if dc_is(0x9F40, 10) then
            do_shot("title")
            phase = "a1"; hold = 16; setk(K.A)
            return
        end
        if f > 8000 then DS_DONE(1, "no-title") end
        return
    end

    if phase == "a1" then phase = "await_menu"; return end

    if phase == "await_menu" then
        if dc_is(0x3140, 8) then
            do_shot("continue_menu")
            phase = "up"; hold = 10; setk(K.UP); wait = 25
            return
        end
        if f > 12000 then DS_DONE(1, "no-menu") end
        return
    end

    if phase == "up" then
        phase = "a2"; hold = 16; setk(K.A); wait = 80
        return
    end

    -- ★ 关键：等 DISPCNT 变成 0x7F60 并稳定（回顾已开始）
    if phase == "a2" then
        if dc_is(0x7F60, 20) then
            do_shot("recap_started")
            RL("[RECAP] started, now press B to skip")
            phase = "press_b"
            bn = 0
            return
        end
        if f > 16000 then
            do_shot("no_recap")
            DS_DONE(1, "no-recap")
        end
        return
    end

    -- 按 B 跳过回顾（少量多次，每次等画面反应）
    if phase == "press_b" then
        bn = bn + 1
        if bn > 10 then
            do_shot("after_b", true)
            RL("[B-DONE] bn=" .. bn)
            phase = "press_start"
            return
        end
        setk(K.B); hold = 10
        wait = 40
        return
    end

    if phase == "press_start" then
        do_shot("before_start", true)
        phase = "menu_open"
        hold = 16; setk(K.START)
        wait = 90
        return
    end

    if phase == "menu_open" then
        do_shot("menu", true)
        phase = "up8"
        stepn = 0
        return
    end

    if phase == "up8" then
        stepn = stepn + 1
        if stepn > 8 then phase = "dn1"; stepn = 0; return end
        hold = 4; setk(K.UP); wait = 10
        return
    end

    if phase == "dn1" then
        stepn = stepn + 1
        if stepn > 1 then phase = "verify"; wait = 30; return end
        hold = 4; setk(K.DOWN); wait = 12
        return
    end

    if phase == "verify" then
        do_shot("on_pokemon")
        phase = "enter"
        hold = 16; setk(K.A)
        wait = 200
        return
    end

    if phase == "enter" then
        do_shot("party", true)
        RL("[PARTY] f=" .. f)
        DS_DONE(0, "party")
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
    r = run_lua(LUA, OUT, expect_files=["s01_title.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<30} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
