#!/usr/bin/env python3
"""调研(118) 换个根本思路：**运行时把每个字的字形抓下来**。

═══════════════════════════════════════════════════════════════════════════
【为什么放弃在 ROM 里找】
═══════════════════════════════════════════════════════════════════════════
已经试遍：
  · 4bpp 原样搜 VRAM 字形 → 151/1197 命中，分散多处，是巧合
  · 1bpp 形式搜 → 146,556 命中，全是假信号
  · nibble ≤3 连续区 → 只剩全 0 的 BSS 段
  · 严格「含 1 且含 2」→ 全 ROM 仅 127 块，无连续区
  · 汉化新增总量 648KB 里，字形类数据只有 30KB（够 236 字）

⇒ **ROM 里没有 2000 字的完整字库。**

【唯一能拿到全部字形的办法：运行时把字都显示一遍】
 火红的中文散布在几百条文本里。要让每个字都出现一次，
 需要把游戏所有文本走一遍 —— 不现实。

【但有个取巧办法：抓「一个字加载进 VRAM 的瞬间」】
 ① 让游戏显示一个文本画面
 ② 每帧 dump VRAM 中「含灰阶」的 tile
 ③ 累积所有出现过的字形 → 字库
 ④ 已经拿到 1197 个（5 个画面）

 ⇒ 继续多走几个画面，能累积到更多。这是**工程可行**的路。

【本脚本：自动走多个菜单/界面，累积字形】
 ① 读档 → 菜单 → 世界 → 各菜单项 → 战斗 → …
 ② 每个稳定画面 dump VRAM
 ③ 累积去重

用法：python scripts/research/firered/118_accumulate_glyphs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "accum"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A, B, START, DOWN, UP, RIGHT = 1, 2, 8, 128, 64, 16
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
local stage = 0
local n = 0

local function setk(m) emu:setKeys(m) end
local function snap(tag)
    n = n + 1
    local base = OUT .. "/g" .. string.format("%02d", n) .. "_" .. tag
    pcall(function()
        local f = assert(io.open(base .. ".vram.bin", "wb"))
        f:write(emu:readRange(0x06000000, 0x18000)); f:close()
    end)
    pcall(function()
        local f = assert(io.open(base .. ".pal.bin", "wb"))
        f:write(emu:readRange(0x05000000, 0x400)); f:close()
    end)
    pcall(function() emu:screenshot(base .. ".png") end)
    RL(string.format("[S%d] %s f=%d dc=%04X", n, tag, RUN.f,
                     emu:read16(0x04000000)))
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end

    if (not proved) and frame > 200 and frame % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true; RL("[PROVE] f=" .. frame)
        end
    end

    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1 else
            last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true; hold = 12; setk(A) end
        if frame > 4000 then DS_DONE(1, "no-save") end
        return
    end

    -- 阶段表：每个阶段「等待 N 帧后做动作 + 抓图」
    local PLAN = {
        { 700,  "act", A,     12, "menu" },
        { 1000, "snap", nil, 0, "world" },
        { 1080, "act", START, 12, "" },
        { 1250, "snap", nil, 0, "startmenu" },
        { 1330, "act", A,     12, "" },
        { 1500, "snap", nil, 0, "poke_menu" },
        { 1580, "act", B,     10, "" },
        { 1660, "act", START, 12, "" },
        { 1730, "act", DOWN,  8,  "" },
        { 1800, "act", A,     12, "" },
        { 1970, "snap", nil, 0, "bag" },
        { 2050, "act", B,     10, "" },
        { 2130, "act", START, 12, "" },
        { 2200, "act", DOWN,  8,  "" },
        { 2230, "act", DOWN,  8,  "" },
        { 2260, "act", DOWN,  8,  "" },
        { 2330, "act", A,     12, "" },
        { 2500, "snap", nil, 0, "option" },
        { 2580, "act", B,     10, "" },
        { 2700, "snap", nil, 0, "world2" },
    }

    if stage < #PLAN then
        local p = PLAN[stage + 1]
        if frame >= p[1] then
            stage = stage + 1
            if p[2] == "snap" then
                snap(p[5])
            else
                setk(p[3]); hold = p[4]
            end
        end
    else
        if frame > 2900 then DS_DONE(0, "done") end
    end
    if frame > 4000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=2700,
                rom=ROM_ZH, save=SAVE_FR, timeout=400,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print(r.log_text)
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
