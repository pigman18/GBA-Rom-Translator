"""调研(228) 在「继续游戏」菜单上选中「继续游戏」项再按 A。

═══ 227 的决定性发现 ═══
s05_menu_on_pokemon 截图显示：
    继续游戏          ← 摘要框
    主角  RED
    时间  22:04
    图鉴  62只
    徽章  7枚
    ┌──────────────┐
    │ 开始新游戏    │ ← **光标停在这里！**
    └──────────────┘

⇒ 「继续游戏」菜单只有 2 项：
    ① 继续游戏（上方摘要框，本身就是"继续"按钮）
    ② 开始新游戏（下方按钮）

我按了 UP×8 + DOWN×1，光标落在第 2 项「开始新游戏」→ 按 A 开了新游戏
→ 弹「操作说明」帮助页。

═══ 正确做法 ═══
在「继续游戏」菜单上：UP 一次把光标移到「继续游戏」，再按 A 读档。

用法：python scripts/research/firered/228_continue_correct.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party228"

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
local last_dc, dc_n = -1, 0
local stepn = 0

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
            phase = "a1"
            hold = 16; setk(K.A)
            return
        end
        if f > 8000 then DS_DONE(1, "no-title") end
        return
    end

    if phase == "a1" then phase = "await_menu"; return end

    if phase == "await_menu" then
        if dc_is(0x3140, 8) then
            do_shot("continue_menu")
            RL("[MENU] at continue-menu")
            phase = "press_up"
            hold = 10; setk(K.UP)   -- 光标移到「继续游戏」
            wait = 25
            return
        end
        if f > 12000 then DS_DONE(1, "no-menu") end
        return
    end

    if phase == "press_up" then
        do_shot("on_continue_item")
        phase = "press_a"
        hold = 16; setk(K.A)
        wait = 350
        return
    end

    if phase == "press_a" then
        do_shot("after_load", true)
        phase = "open_menu"
        hold = 16; setk(K.START)
        wait = 90
        return
    end

    if phase == "open_menu" then
        do_shot("start_menu", true)
        phase = "menu_up"
        stepn = 0
        return
    end

    if phase == "menu_up" then
        stepn = stepn + 1
        if stepn > 8 then phase = "menu_down"; stepn = 0; return end
        hold = 4; setk(K.UP)
        wait = 10
        return
    end

    if phase == "menu_down" then
        stepn = stepn + 1
        if stepn > 1 then phase = "menu_ready"; wait = 30; return end
        hold = 4; setk(K.DOWN)
        wait = 12
        return
    end

    if phase == "menu_ready" then
        do_shot("menu_on_pokemon")
        phase = "enter_party"
        hold = 16; setk(K.A)
        wait = 180
        return
    end

    if phase == "enter_party" then
        do_shot("party", true)
        RL("[PARTY] f=" .. f)
        DS_DONE(0, "party")
        return
    end

    if f > 30000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_title.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=520)
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<32} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
