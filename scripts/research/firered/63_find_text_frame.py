#!/usr/bin/env python3
"""调研(63) 用正确的 IO 偏移读 tilemap，看到屏幕上的真实汉字 tile。

═══════════════════════════════════════════════════════════════════════════
【已确认的 IO 真实布局（(62) 实测，与 ROM 对照验证读法正确）】
═══════════════════════════════════════════════════════════════════════════
  0x04000000 +0x00 DISPCNT   = 0x5C40 (标题) / 0x3140 (菜单)
             +0x02 DISPSTAT  = 0x0000
             +0x04 VCOUNT*(读时抖动，忽略)
             +0x06 0x00A0
             +0x08 BG0CNT    = 0x0007
             +0x0A BG1CNT    = 0x0000
             +0x0C BG2CNT    = 0x0E1E
             +0x0E BG3CNT    = 0x0F1F

  ⚠ 注意：BG0CNT 在 **+0x08**（不是 +0x08+b*2 才有问题，那里也对），
     但要小心 BGxHOFS 在 +0x10 之后的读数是「01 BC 01 BC」重复 ——
     这不是 HOFS。实测 0x04000010 = 0x04000010 是 **BG0HOFS**，
     但 mGBA 读出来是 0x01BC，说明这块区域被别的东西覆盖了，
     或者 mGBA 对 0x04000010..0x0400002F 的读取有特殊行为。
     **结论：只信 +0x00..+0x0F 这段（已被 ROM 对照验证过）。**

【DISPCNT=0x3140 到底开没开 BG】
   0x3140 = 0011 0001 0100 0000b
   bit0-3 = 0000  BG0~BG3 全关
   bit4   = 0     OBJ 关
   bit5   = 0     WIN0 关
   bit6   = 1     WIN1 开
   bit7   = 0     OBJWIN 关
   bit8   = 1
   bit9   = 0
   bit10  = 0
   bit11  = 0
   bit12  = 1
   bit13-15 = 001  BG mode = 1

   ⇒ **BG mode 1（混合）+ WIN1 开 + BG 全关**。
   这在「继续游戏」菜单上不可能。除非 —— 这个状态其实在**转场**。

【本脚本的做法】
   不猜，直接：
    ① 重采，并且**每帧记录 DISPCNT**，找出「BG0 开着」的帧
    ② 对 BG0 开着的帧，读它的 tilemap 并画出前几行
    ③ 看到汉字 tile 后，直接量字宽

用法：python scripts/research/firered/63_find_text_frame.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "textframe"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local proved, hold, phase = false, 0, "boot"
local A = 1
local function setk(m) emu:setKeys(m) end

-- 每帧记录 DISPCNT，找 BG0 开着的帧
local hist = {}
local saved = 0

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f

    local dc = emu:read16(0x04000000)
    if frame % 20 == 0 then
        hist[#hist+1] = string.format("%d:%04X", frame, dc)
    end

    if (not proved) and frame % 60 == 0 and frame > 240 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] f=" .. frame)
        end
    end

    if frame == 360 then setk(A); hold = 10; phase = "t1" end
    if phase == "t1" then hold = hold - 1; if hold <= 0 then setk(0); phase="w1" end
    elseif phase == "w1" and frame > 460 then setk(A); hold = 10; phase="t2"
    elseif phase == "t2" then hold = hold - 1; if hold <= 0 then setk(0); phase="w2" end
    elseif phase == "w2" and frame > 640 then setk(A); hold = 10; phase="t3"
    elseif phase == "t3" then hold = hold - 1; if hold <= 0 then setk(0); phase="wait" end
    end

    -- 只抓 BG0 真开着的帧
    if proved and saved < 6 and (dc & 1) == 1 then
        saved = saved + 1
        local tag = OUT .. "/t" .. saved
        local SEGS = {
            { suf = ".vram.bin", addr = 0x06000000, len = 0x18000 },
            { suf = ".pal.bin",  addr = 0x05000000, len = 0x400 },
            { suf = ".io.bin",   addr = 0x04000000, len = 0x10 },
            { suf = ".oam.bin",  addr = 0x07000000, len = 0x400 },
        }
        for _, S in ipairs(SEGS) do
            pcall(function()
                local blob = emu:readRange(S.addr, S.len)
                local fp = assert(io.open(tag .. S.suf, "wb"))
                fp:write(blob); fp:close()
            end)
        end
        pcall(function() emu:screenshot(tag .. ".png") end)
        RL(string.format("[T%d] f=%d dispcnt=%04X", saved, frame, dc))
    end

    if proved and frame > 1600 then
        RL("[HIST] " .. table.concat(hist, " "))
        DS_DONE(0, "done")
    end
    if frame > 3000 then DS_DONE(1, "timeout") end
end))
'''

EXPECT = []
for i in range(1, 7):
    EXPECT += [f"t{i}.vram.bin", f"t{i}.png"]


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=1000,
                rom=ROM_ZH, save=SAVE_FR, timeout=400,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print(r.log_text)
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
