#!/usr/bin/env python3
"""调研(70) 加入窗口(WIN1)与混合(blend)后再还原 —— mode 1 + WIN1 是关键。

═══════════════════════════════════════════════════════════════════════════
【(69) 漏了什么】
═══════════════════════════════════════════════════════════════════════════
DISPCNT = 0x3140：
    mode = 1     ← GBA mode 1 = BG0/BG1 用 4bpp、BG2 用 8bpp
    bit6 = 1     ← **WIN1 使能**（只显示窗口内的东西）
    bit0-3 = 0   ← BG 层未使能
    bit4 = 0     ← OBJ 未使能

我的渲染器：
  · 没有处理 WIN1（不知道窗口范围）
  · 没有处理 alpha blend / 亮度混合
  · BG 层使能位是 0 就没渲染 —— 但这可能是**读到的值**问题

关键：**GBA 在 mode 1 下，即使 bit0 为 0，也不影响「窗口内」的显示逻辑吗？不是。**
      BG 层使能位为 0，那层就真的不显示。

⇒ 必须面对一个前提：**DISPCNT 读到的 0x3140 可能真的不是当前值。**

理由：我在 frame 回调里读 IO，但 mGBA 的 frame 回调时机可能在
「帧末 VBlank」，此时游戏可能已经把 DISPCNT 改成了下一帧要用的值。
菜单界面的 DISPCNT 会是「BG 开着」，而 VBlank 时被改成过渡值。

═══════════════════════════════════════════════════════════════════════════
【验证：读 IO 的时机】
═══════════════════════════════════════════════════════════════════════════
在一个 frame 回调里，**同一帧内多次读 DISPCNT**（中间插入忙等），
若值会变 ⇒ 说明 IO 是实时的、我抓的时刻在过渡中。
若值恒定 ⇒ 那 0x3140 就是这一帧的真实值，必须另找原因。

同时用 mGBA 的 `emu:screenshotTiles()` 或分帧对比来定位。

先做最简单有效的：**在 frame 回调里读 100 次 DISPCNT，记录是否变化。**

用法：python scripts/research/firered/70_window_and_timing.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "timing"
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
local phase = 0

local function setk(m) emu:setKeys(m) end

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

    -- 读档后，在**同一帧回调**里密集读 DISPCNT 200 次
    if frame == 700 and phase == 0 then
        phase = 1
        local vals = {}
        local uniq = {}
        local seen = {}
        for i = 1, 200 do
            local ok, v = pcall(function() return emu:read16(0x04000000) end)
            if ok then
                vals[#vals+1] = v
                if not seen[v] then
                    seen[v] = true
                    uniq[#uniq+1] = string.format("%04X", v)
                end
            end
        end
        RL("[DENSE200] 不同值: " .. table.concat(uniq, " "))
        RL("[DENSE200] 前20次: " .. table.concat(
            (function() local t={} for i=1,20 do t[i]=string.format("%04X",vals[i]) end return t end)(),
            " "))

        -- 同时读 BGxCNT
        RL(string.format("[BG] %04X %04X %04X %04X",
            emu:read16(0x04000008), emu:read16(0x0400000A),
            emu:read16(0x0400000C), emu:read16(0x0400000E)))

        -- 读 WIN1 相关寄存器：WIN1H(0x04000042) WIN1V(0x04000044)
        RL(string.format("[WIN1] H=%04X V=%04X WININ=%04X WINOUT=%04X",
            emu:read16(0x04000042), emu:read16(0x04000044),
            emu:read16(0x04000048), emu:read16(0x0400004A)))

        -- BLDCNT / BLDALPHA / BLDY
        RL(string.format("[BLD] CNT=%04X ALPHA=%04X Y=%04X",
            emu:read16(0x04000050), emu:read16(0x04000052),
            emu:read16(0x04000054)))

        DS_DONE(0, "dense")
    end
    if frame > 1200 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=600,
                rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- 密集读取 ---")
    for line in r.log_text.splitlines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
