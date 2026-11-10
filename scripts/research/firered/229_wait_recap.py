"""调研(229) 读档后等冒险回顾播完，再 START 开菜单进队伍。

═══ 228 已突破 ═══
读档成功！DISPCNT 0x7F60 = 野外，随后进入「冒险回顾」过场（截图确认：
红莲镇道馆 + 底部旁白小字）。

现在只需要：**等回顾自己播完**（它会自动翻页/推进），然后 START 开菜单。

判据「回顾结束」：
  · DISPCNT 从 0x7F60 变化后重新稳定，且截图不再是回顾画面
  · 更稳：等足够长（回顾通常 5~10 秒），然后 START

本脚本：
 ① await 0x9F40 标题 → A
 ② await 0x3140 菜单 → UP → A（选「继续游戏」）
 ③ 等 1200 帧（约 20 秒）让回顾播完，期间分阶段截图
 ④ START → UP×8 → DOWN → A → 队伍

用法：python scripts/research/firered/229_wait_recap.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party229"

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
    local bg0 = rd16(0x04000008)
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
    RL(string.format("[SHOT] %02d %-16s dispcnt=0x%04X bg0=0x%04X f=%d",
                     shotn, name, dc, bg0, RUN.f))
end

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local stepn = 0
local recap_n = 0

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
        phase = "a2"; hold = 16; setk(K.A); wait = 60
        return
    end

    if phase == "a2" then
        do_shot("loading")
        phase = "recap_wait"
        wait = 240
        return
    end

    -- 等回顾播完：每 240 帧截一张，共 5 次
    if phase == "recap_wait" then
        recap_n = recap_n + 1
        do_shot("recap" .. string.format("%02d", recap_n))
        if recap_n >= 5 then
            phase = "try_start"
            hold = 16; setk(K.START)
            wait = 100
            return
        end
        wait = 240
        return
    end

    if phase == "try_start" then
        do_shot("after_start", true)
        phase = "menu_nav"
        stepn = 0
        return
    end

    if phase == "menu_nav" then
        stepn = stepn + 1
        if stepn > 8 then phase = "menu_dn"; stepn = 0; return end
        hold = 4; setk(K.UP); wait = 10
        return
    end

    if phase == "menu_dn" then
        stepn = stepn + 1
        if stepn > 1 then phase = "menu_ok"; wait = 30; return end
        hold = 4; setk(K.DOWN); wait = 12
        return
    end

    if phase == "menu_ok" then
        do_shot("menu_on_pokemon")
        phase = "enter"; hold = 16; setk(K.A); wait = 200
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
    print(r.log_text[-3500:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<32} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
