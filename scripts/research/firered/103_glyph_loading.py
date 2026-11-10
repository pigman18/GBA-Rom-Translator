#!/usr/bin/env python3
"""调研(103) 运行时抓字库加载 —— 让画面显示更多字，看 VRAM 里字形是否变化。

═══════════════════════════════════════════════════════════════════════════
【思路】
═══════════════════════════════════════════════════════════════════════════
(101) 证明 VRAM 只装当前帧的字（~47 个）。
若能证明「换一个画面 → VRAM 里的字形集合也换」，
就确认是**按需加载**，那么完整字库必然在 ROM 或生成算法里。

【做法：采多个不同画面的 VRAM，比对字形集合】
 ① 读档进菜单（画面 A）→ dump
 ② 按 A 进游戏世界 → dump
 ③ 打开 START 菜单 → dump
 ④ 进背包 → dump
 ⑤ 每个画面统计「含灰阶 tile 的内容哈希集合」
 ⑥ 看这些集合是否**互不重叠**

 若互不重叠 ⇒ 字形按需加载 ⇒ 全字库在 ROM
 若大量重叠 ⇒ 有一份常驻字库在 VRAM

用法：python scripts/research/firered/103_glyph_loading.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "glyphload"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A, B, START, DOWN, UP = 1, 2, 8, 128, 64
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
local stage = 0
local shots = 0

local function setk(m) emu:setKeys(m) end
local function save(p, addr, len)
    pcall(function()
        local b = emu:readRange(addr, len)
        local f = assert(io.open(p, "wb")); f:write(b); f:close()
    end)
end
local function snap(tag)
    shots = shots + 1
    local base = OUT .. "/" .. tag
    save(base .. ".vram.bin", 0x06000000, 0x18000)
    save(base .. ".pal.bin", 0x05000000, 0x400)
    save(base .. ".io.bin", 0x04000000, 0x10)
    pcall(function() emu:screenshot(base .. ".png") end)
    RL(string.format("[SNAP %s] f=%d dc=%04X", tag, RUN.f,
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

    -- 读档后按阶段推进，每个阶段抓一张
    if frame == 700 and stage == 0 then
        stage = 1
        snap("A_menu")
    elseif frame == 780 and stage == 1 then
        stage = 2
        setk(A); hold = 12          -- 进入游戏世界
    elseif frame == 1100 and stage == 2 then
        stage = 3
        snap("B_world")
    elseif frame == 1180 and stage == 3 then
        stage = 4
        setk(START); hold = 12      -- 打开 START 菜单
    elseif frame == 1330 and stage == 4 then
        stage = 5
        snap("C_start")
    elseif frame == 1410 and stage == 5 then
        stage = 6
        setk(DOWN); hold = 8        -- 往下选
    elseif frame == 1480 and stage == 6 then
        stage = 7
        snap("D_down")
    elseif frame == 1560 and stage == 7 then
        stage = 8
        setk(B); hold = 8           -- 返回
    elseif frame == 1700 and stage == 8 then
        stage = 9
        snap("E_back")
        DS_DONE(0, "done")
    end
    if frame > 2500 then DS_DONE(1, "late") end
end))
'''

EXPECT = []
for tag in ("A_menu", "B_world", "C_start", "D_down", "E_back"):
    EXPECT += [f"{tag}.vram.bin", f"{tag}.png"]


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=1700,
                rom=ROM_ZH, save=SAVE_FR, timeout=400,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print(r.log_text)
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
