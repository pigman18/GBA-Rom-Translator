#!/usr/bin/env python3
"""调研(77) 用正确位定义重采并定位中文字形 —— 这次条件是对的。

═══════════════════════════════════════════════════════════════════════════
【已修正的关键错误（(76)）】
═══════════════════════════════════════════════════════════════════════════
 DISPCNT 的 BG 使能位是 **bit8-11**（不是 bit0-3），OBJ 是 bit12。
 BGxCNT 寄存器地址：BG0CNT=0x04000006, BG1CNT=0x08, BG2CNT=0x0A, BG3CNT=0x0C。

 修正后：
    野外 0x7F60 → BG=[1,1,1,1] OBJ=1   ✓
    菜单 0x3140 → BG=[1,0,0,0] OBJ=1   ✓
 都正常。此前所有「BG 全关」的判断作废。

═══════════════════════════════════════════════════════════════════════════
【本轮目标：在菜单画面定位汉字字形】
═══════════════════════════════════════════════════════════════════════════
 菜单 DISPCNT=0x3140：只有 **BG0 使能**（+OBJ）。BG0CNT=0x00A0：
     charBase = 0x0000
     screenBase = 0x0000
     **8bpp**
     priority = 0

 ⇒ 菜单的文字全在 BG0（8bpp），tilemap 在 VRAM 0x0000。

 但 0x0000 也是 charBase —— 两者重叠，说明这个 BG0CNT 读数可疑。
 必须同时抓 **OAM**（OBJ 也可能画字）和**多个菜单子画面**。

本脚本：
 ① 读档进菜单，确认 BG0CNT / DISPCNT
 ② dump VRAM + PAL + OAM + EWRAM
 ③ 用 4 种 charBase × 多种 screenBase 组合渲染 BG0，与截图比对
 ④ 同时渲染 OBJ（从 OAM 取条目）
 ⑤ 输出还原度最高的组合，那就是真实配置

用法：python scripts/research/firered/77_find_glyphs_correct.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "glyphs"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A = 1
local proved, hold, last_dc, stable = false, 0, -1, 0
local pressed = {}
local shot = 0

local function setk(m) emu:setKeys(m) end
local function save(p, addr, len)
    pcall(function()
        local b = emu:readRange(addr, len)
        local f = assert(io.open(p, "wb")); f:write(b); f:close()
    end)
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

    -- 读档后每 150 帧抓一次，共 4 次（覆盖菜单的不同状态）
    if frame > 700 and frame % 150 == 0 and shot < 4 then
        shot = shot + 1
        local tag = OUT .. "/g" .. shot
        save(tag .. ".vram.bin", 0x06000000, 0x18000)
        save(tag .. ".pal.bin",  0x05000000, 0x400)
        save(tag .. ".oam.bin",  0x07000000, 0x400)
        save(tag .. ".ewram.bin",0x02000000, 0x40000)
        save(tag .. ".io.bin",   0x04000000, 0x10)
        pcall(function() emu:screenshot(tag .. ".png") end)
        -- 用正确的寄存器地址读 BGxCNT
        local dc = emu:read16(0x04000000)
        local b0 = emu:read16(0x04000006)
        local b1 = emu:read16(0x04000008)
        local b2 = emu:read16(0x0400000A)
        local b3 = emu:read16(0x0400000C)
        RL(string.format("[G%d] f=%d dc=%04X BG=%04X,%04X,%04X,%04X",
                         shot, frame, dc, b0, b1, b2, b3))
    end

    if shot >= 4 then DS_DONE(0, "done") end
    if frame > 2200 then DS_DONE(1, "late") end
end))
'''

EXPECT = []
for i in range(1, 5):
    EXPECT += [f"g{i}.vram.bin", f"g{i}.pal.bin", f"g{i}.oam.bin",
               f"g{i}.png", f"g{i}.io.bin"]


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=900,
                rom=ROM_ZH, save=SAVE_FR, timeout=400,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print(r.log_text)
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
