#!/usr/bin/env python3
"""调研(67) 用「GBA 硬件常量」当标尺，定位 IO 读取到底错在哪。

═══════════════════════════════════════════════════════════════════════════
【当前死结】
═══════════════════════════════════════════════════════════════════════════
  · 24 帧连续稳定：DISPCNT=0x3140，BG0-3=0000（全关）
  · 但截图确实是中文菜单
  · IO 读法已验证可信（KEYINPUT 按 A 时 bit0 正确清零，VCOUNT=0x0A0 合法）

三者同时成立在硬件上不可能。

═══════════════════════════════════════════════════════════════════════════
【新思路：用「屏幕确实显示」反推正确的寄存器值】
═══════════════════════════════════════════════════════════════════════════
GBA 上若要显示文字，DISPCNT 必须至少有 BG0-3 之一或 OBJ 打开。
实测读到 0x3140 全关 ⇒ 读到的**不是真正的 DISPCNT**。

那 mGBA 的 emu:read16(0x04000000) 到底读到哪了？

做法：**扫描地址空间**。从 0x04000000 开始，每 4 字节读一次 u16，
看有没有哪个位置的值「像真正的 DISPCNT」（bit0-3 至少一个 1）。

同时对照 KEYINPUT 已知真值 0x03FF：
  在 0x04000000..0x04000400 里找哪个地址读到 0x03FF，
  就知道 IO 区被映射到了哪 —— 这是**用已知真值定位映射偏移**，
  比继续猜 DISPCNT 可靠。

用法：python scripts/research/firered/67_locate_io_mapping.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "iomap"
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
local done = false

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

    if frame > 400 and not done then
        done = true

        -- ① 扫 0x04000000..0x04000200，每 2 字节读一次
        --    找「值 == 0x03FF」的位置（KEYINPUT 的空闲值，已知真值）
        local hits = {}
        local vals = {}
        for off = 0, 0x200, 2 do
            local ok, v = pcall(function() return emu:read16(0x04000000 + off) end)
            if ok then
                vals[#vals+1] = string.format("%03X:%04X", off, v)
                if v == 0x03FF then
                    hits[#hits+1] = string.format("0x%03X", off)
                end
            end
        end
        RL("[KEYSCAN 0x03FF] " .. (#hits > 0 and table.concat(hits, " ") or "无"))
        -- 只吐前 64 个 value 免得日志爆
        RL("[VALSCAN] " .. table.concat(vals, " ", 1, 64))

        -- ② 扫 0x04000300..0x04000400（IE/IF/IME/WAITCNT 区）
        local v2 = {}
        for off = 0x130, 0x140, 2 do
            local ok, v = pcall(function() return emu:read16(0x04000000 + off) end)
            if ok then v2[#v2+1] = string.format("%03X:%04X", off, v) end
        end
        RL("[keyinput area] " .. table.concat(v2, " "))

        -- ③ 直接读 KEYINPUT 并同时按 A，确认它动的就是这里
        local k0 = emu:read16(0x04000130)
        emu:setKeys(A)
        local k1 = emu:read16(0x04000130)
        emu:setKeys(0)
        RL(string.format("[KEYINPUT] idle=%04X down=%04X", k0, k1))

        -- ④ 扫「哪里读到 0x0A0」（VCOUNT 实测值）
        local vhits = {}
        for off = 0, 0x200, 2 do
            local ok, v = pcall(function() return emu:read16(0x04000000 + off) end)
            if ok and v == 0x0A0 then vhits[#vhits+1] = string.format("0x%03X", off) end
        end
        RL("[VCOUNT 0x0A0 出现处] " .. (#vhits > 0 and table.concat(vhits, " ") or "无"))

        DS_DONE(0, "scanned")
    end
    if frame > 900 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=400,
                rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- 扫描结果 ---")
    for line in r.log_text.splitlines():
        print(line[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
