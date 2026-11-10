"""调研(227) await 状态驱动：标题(0x9F40) → A → 继续游戏(0x3140) → A → 野外 → START → 队伍。

═══ 226 揭示的真实流程 ═══
  f=545  dispcnt=0x9F40  ← **标题画面**（已截图确认：Charizard + POKEMON 火红 logo）
  f=640  dispcnt=0x9F40  ← 仍在标题（UP/DOWN 在标题上无效）
  f=839  dispcnt=0x3140  ← **「继续游戏」菜单**（按 A 之后才出现）

⇒ 流程是：标题 --A--> 继续游戏菜单 --A--> 读档进野外

226 只按了一次 A（把它花在了 UP/DOWN 上），所以停在菜单。

═══ 本脚本（照 _lib.lua 的 await 写法）═══
  ① await DISPCNT==0x9F40（标题站稳）
  ② A → await DISPCNT==0x3140（继续游戏菜单）
  ③ A → wait 400（读档淡入）→ shot 野外（记录它的 DISPCNT）
  ④ START → shot 菜单
  ⑤ UP×8 → DOWN×1 → shot（光标在「宝可梦」）
  ⑥ A → wait 200 → shot + 全量 dump（队伍）

⚠ 全程不按 B（_lib.lua 明确记载：读档序列夹 B 会退回标题）

用法：python scripts/research/firered/227_party_await.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party227"

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

-- 状态机需要的运行变量
local phase = "await_title"
local hold, wait = 0, 0
local stepn = 0
local last_dc, dc_stable = -1, 0

-- await 帮助：DISPCNT 连续 K 帧等于目标（且画面稳定）
local function dc_is(want, k)
    local dc = rd16(0x04000000)
    if dc == want then dc_stable = dc_stable + 1 else dc_stable = 0 end
    return dc_stable >= (k or 8)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    if phase == "await_title" then
        if dc_is(0x9F40, 10) then
            do_shot("title")
            RL("[TITLE] stable f=" .. f)
            phase = "press_a1"
            hold = 16; setk(K.A)
            return
        end
        if f > 8000 then DS_DONE(1, "no-title") end
        return
    end

    if phase == "press_a1" then
        phase = "await_menu"
        return
    end

    if phase == "await_menu" then
        if dc_is(0x3140, 8) then
            do_shot("continue_menu")
            RL("[MENU] continue-menu f=" .. f)
            phase = "press_a2"
            hold = 16; setk(K.A)
            return
        end
        if f > 12000 then
            do_shot("no_menu")
            DS_DONE(1, "no-menu")
        end
        return
    end

    if phase == "press_a2" then
        phase = "await_map"
        wait = 400
        return
    end

    if phase == "await_map" then
        -- 读档后画面会变化；等它稳定下来
        do_shot("after_load", true)
        phase = "press_start"
        hold = 16; setk(K.START)
        wait = 80
        return
    end

    if phase == "press_start" then
        do_shot("menu_open")
        phase = "menu_up"
        stepn = 0
        return
    end

    if phase == "menu_up" then
        stepn = stepn + 1
        if stepn > 8 then
            phase = "menu_down"
            stepn = 0
            return
        end
        hold = 4; setk(K.UP)
        wait = 10
        return
    end

    if phase == "menu_down" then
        stepn = stepn + 1
        if stepn > 1 then
            phase = "menu_ready"
            wait = 30
            return
        end
        hold = 4; setk(K.DOWN)
        wait = 12
        return
    end

    if phase == "menu_ready" then
        do_shot("menu_on_pokemon")
        phase = "press_a3"
        hold = 16; setk(K.A)
        wait = 150
        return
    end

    if phase == "press_a3" then
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
