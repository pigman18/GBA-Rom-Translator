#!/usr/bin/env python3
"""调研(68) 破局：用 PNG 像素反证 DISPCNT —— 到底哪一边错了。

═══════════════════════════════════════════════════════════════════════════
【现状：三个事实互相矛盾】
═══════════════════════════════════════════════════════════════════════════
  F1 DISPCNT = 0x3140，bit0-4 全 0（BG0-3 + OBJ 全关）—— 24 帧稳定，读取位置
     已验证正确（KEYINPUT@0x130=0x03FF、VCOUNT@0x006=0x00A0 都在正确地址）
  F2 截图 probe.png 确实显示中文菜单 —— 肉眼确认
  F3 GBA 硬件上 DISPCNT bit0-4 全 0 ⇒ 输出 force blank（空白）

⇒ 三选一必然有一个是假的。

═══════════════════════════════════════════════════════════════════════════
【关键测试：在图里找 GBA 标志性结构】
═══════════════════════════════════════════════════════════════════════════
若截图真是「当前帧」，它必然由 VRAM 里的 tile 画成。
所以：**把 VRAM 按各种 charBase/screenBase 组合解析，看哪种能还原出截图**。

这不是猜 —— 是**穷举 4×32 种组合，逐一比对截图像素**，命中的就是真配置。
若没有任何组合能还原 ⇒ 截图与 VRAM 不同帧（采集时序问题）。

做法：
 ① 从 PNG 读像素（按 GBA 调色板转回索引色）
 ② 对 DISPCNT 的每种 mode（0..5）× 每层 charBase(0-3) × screenBase(0-31)
 ③ 渲染出 240×160，与 PNG 比相似度
 ④ 相似度最高的组合 = 真实配置

这能一次性回答：DISPCNT 读错了？还是截图不同帧？

用法：python scripts/research/firered/68_prove_by_render.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "renderprove"
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
local grabbed = false

local function setk(m) emu:setKeys(m) end

local function save(path, blob)
    local ok = pcall(function()
        local fp = assert(io.open(path, "wb"))
        fp:write(blob); fp:close()
    end)
    return ok
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

    -- 读档后等 120 帧再抓，确保画面彻底稳定
    if frame > 700 and not grabbed then
        grabbed = true
        -- 同一帧内：先读所有内存，最后截图
        save(OUT .. "/a.vram.bin", emu:readRange(0x06000000, 0x18000))
        save(OUT .. "/a.pal.bin",  emu:readRange(0x05000000, 0x400))
        save(OUT .. "/a.oam.bin",  emu:readRange(0x07000000, 0x400))
        save(OUT .. "/a.io.bin",   emu:readRange(0x04000000, 0x60))
        local dc = emu:read16(0x04000000)
        RL(string.format("[GRAB] f=%d dc=%04X", frame, dc))

        -- 再抓一次，隔 2 帧，看是否一致
        DS_DONE(0, "grabbed")
    end
    if frame > 1500 then DS_DONE(1, "late") end
end))
'''

LUA2 = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A = 1
local proved, hold, last_dc, stable = false, 0, -1, 0
local pressed = {}
local step = 0

local function setk(m) emu:setKeys(m) end
local function save(p, b)
    pcall(function() local f = assert(io.open(p, "wb")); f:write(b); f:close() end)
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

    if frame > 700 and step == 0 then
        step = 1
        -- ★ 先截图（此刻画面已渲染完成），再读内存
        pcall(function() emu:screenshot(OUT .. "/shotA.png") end)
        save(OUT .. "/A.vram.bin", emu:readRange(0x06000000, 0x18000))
        save(OUT .. "/A.pal.bin",  emu:readRange(0x05000000, 0x400))
        save(OUT .. "/A.io.bin",   emu:readRange(0x04000000, 0x60))
        RL(string.format("[A] f=%d dc=%04X", frame, emu:read16(0x04000000)))
    elseif frame > 760 and step == 1 then
        step = 2
        pcall(function() emu:screenshot(OUT .. "/shotB.png") end)
        save(OUT .. "/B.vram.bin", emu:readRange(0x06000000, 0x18000))
        save(OUT .. "/B.pal.bin",  emu:readRange(0x05000000, 0x400))
        save(OUT .. "/B.io.bin",   emu:readRange(0x04000000, 0x60))
        RL(string.format("[B] f=%d dc=%04X", frame, emu:read16(0x04000000)))
        DS_DONE(0, "done")
    end
    if frame > 1500 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA2, OUT,
                expect_files=["shotA.png", "A.vram.bin", "A.pal.bin"],
                min_frames=700, rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print(r.log_text)
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
