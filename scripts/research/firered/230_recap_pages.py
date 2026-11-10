"""调研(230) 在冒险回顾里用 A 连翻，直到退出。

═══ 229 观察 ═══
回顾画面在 1200 帧内没有自动播完（s04~s08 都不一样，说明它在翻页），
按 START 后又回到第 1 页（s11 显示「冒险回顾 1」）。

⇒ 回顾是**手动翻页**的多页过场：A = 下一页。

本脚本：读档后在回顾里**连按 A**，每按一次截一张，
直到画面离开回顾（DISPCNT 或画面特征变化）。
然后 START → 菜单 → 队伍。

判据「离开回顾」：截图尺寸/内容大幅变化，且 DISPCNT 保持 0x7F60
                  —— 更简单：按 A 20 次，每次截图，事后人工核对。

用法：python scripts/research/firered/230_recap_pages.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party230"

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
    RL(string.format("[SHOT] %02d %-14s dc=0x%04X f=%d", shotn, name, dc, RUN.f))
end

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local pn = 0

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
            phase = "a1"; hold = 16; setk(K.A); return
        end
        if f > 8000 then DS_DONE(1, "no-title") end
        return
    end
    if phase == "a1" then phase = "await_menu"; return end
    if phase == "await_menu" then
        if dc_is(0x3140, 8) then
            phase = "up"; hold = 10; setk(K.UP); wait = 25; return
        end
        if f > 12000 then DS_DONE(1, "no-menu") end
        return
    end
    if phase == "up" then
        phase = "a2"; hold = 16; setk(K.A); wait = 100; return
    end

    -- 在回顾里连按 A，每页截一张
    if phase == "a2" then
        pn = pn + 1
        do_shot("p" .. string.format("%02d", pn), pn == 1)
        if pn > 22 then
            RL("[PAGE-DONE] pn=" .. pn)
            DS_DONE(0, "pages")
        end
        hold = 16; setk(K.A)
        wait = 90
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
    r = run_lua(LUA, OUT, expect_files=["s01_p01.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<22} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
