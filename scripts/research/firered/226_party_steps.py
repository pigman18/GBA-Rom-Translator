"""调研(226) 步骤序列式（照抄 _lib.lua 的 API 结构），干净地进队伍。

═══ 设计说明 ═══
_lib.lua 的做法是**先构造步骤列表，再逐步执行**，每步之后等画面稳定。
本脚本把同一套结构搬到火红，步骤列表：

  1. wait(120)                    等标题
  2. A  × 6  (每步 wait 40)       过标题/版权/读档确认
  3. wait(300)                    等读档淡入
  4. shot "overworld"
  5. START                        开菜单
  6. UP × 8                       到顶
  7. DOWN × 1                     到「宝可梦」
  8. shot "menu_on_pokemon"
  9. A                            进入
  10. wait(150)
  11. shot "party" + dump

⚠ 全程不按 B。

用法：python scripts/research/firered/226_party_steps.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party226"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."

-- 按键位（mGBA setKeys 位掩码）
local K = { A = 1, B = 2, SELECT = 4, START = 8,
            RIGHT = 16, LEFT = 32, UP = 64, DOWN = 128, R = 256, L = 512 }

local function build()
    local S = {}
    local function add(t) S[#S + 1] = t; return t end
    local function key(k, hold, wait)
        add{ act = "key", key = k, hold = hold or 16, wait = wait or 0 }
    end
    local function wait(n) add{ act = "wait", n = n } end
    local function shot(name, dump)
        add{ act = "shot", name = name, dump = dump or false }
    end

    wait(120)                       -- 等标题
    for i = 1, 6 do key("A", 16, 45) end   -- 过标题/确认/读档
    wait(320)                       -- 读档淡入
    shot("overworld")               -- 应到野外

    key("START", 16, 70)            -- 开菜单
    shot("menu_open")
    for i = 1, 8 do key("UP", 4, 10) end   -- 到顶
    key("DOWN", 4, 14)              -- 到「宝可梦」(index 2)
    wait(30)
    shot("menu_on_pokemon")
    key("A", 16, 60)                -- 进入队伍
    wait(180)
    shot("party", true)             -- 队伍界面 + dump
    return S
end

local STEPS = build()
local idx = 0
local hold, wait = 0, 0
local shotn = 0
local lastv, stable = nil, 0

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

local function do_shot(name, dump)
    shotn = shotn + 1
    local i = string.format("%02d", shotn)
    local dc = rd16(0x04000000)
    local bg0 = rd16(0x04000008)
    emu:screenshot(OUTP .. "/s" .. i .. "_" .. name .. ".png")
    if dump then
        for _, spec in ipairs({
            { "vram", 0x06000000, 0x18000 },
            { "ewram", 0x02000000, 0x40000 },
            { "iwram", 0x03000000, 0x8000 },
            { "pal", 0x05000000, 0x400 },
        }) do
            local d = rd(spec[2], spec[3])
            if d then wr("s" .. i .. "_" .. name .. "_" .. spec[1] .. ".bin", d) end
        end
    end
    RL(string.format("[SHOT] %02d %-16s dispcnt=0x%04X bg0=0x%04X f=%d",
                     shotn, name, dc, bg0, RUN.f))
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    if idx >= #STEPS then
        RL("[ALLDONE] f=" .. f)
        DS_DONE(0, "steps-done")
        return
    end

    idx = idx + 1
    local s = STEPS[idx]
    if s.act == "wait" then
        wait = s.n
        RL("[STEP " .. idx .. "] wait " .. s.n)
    elseif s.act == "key" then
        hold = s.hold
        setk(K[s.key])
        if s.wait and s.wait > 0 then
            -- hold 结束后再 wait：用两步表示
            wait = 0
            STEPS[idx].pending_wait = s.wait
        end
        RL("[STEP " .. idx .. "] key " .. s.key)
    elseif s.act == "shot" then
        do_shot(s.name, s.dump)
    end

    if f > 40000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_overworld.png"], min_frames=800,
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
