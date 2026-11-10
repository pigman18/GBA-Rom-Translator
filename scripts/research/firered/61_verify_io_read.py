#!/usr/bin/env python3
"""调研(61) 验证 emu:readRange 读 IO 是否正确 —— 用两种方式交叉验证。

═══════════════════════════════════════════════════════════════════════════
【疑点】
═══════════════════════════════════════════════════════════════════════════
  · d1 的 io.bin 前 8 字节 = 40 5c 00 00 → DISPCNT=0x5C40（s1 是 0x3140）
  · 但 d1 那批是 51 号脚本（不按键、停标题），s1 是 55 号（按键读档）
  · 两者 DISPCNT 差很多虽合理，可 s1 的 +0x10 起是 00 28 00 28 重复，
    而 d1 的 +0x10 起是 01 bc 01 bc 重复 —— 都不是正常 HOFS/VOFS

⇒ 必须验证：emu:readRange(0x04000000, 0x60) 到底给了什么？
   用 emu:read16 逐寄存器读，与 readRange 结果对比。

如果两者一致，说明 IO 区就是这么读的（可能 mGBA 把整个 IO 区映射成别的）；
如果不一致，说明 readRange 有坑。

═══════════════════════════════════════════════════════════════════════════
【顺带解决的真问题】
═══════════════════════════════════════════════════════════════════════════
 读档后 BG 全关是**不可能**的（画面明明有中文菜单）。
 所以要么 IO 读错，要么我读的时刻不对。
 本脚本在**同一个 callback 内**连续读 DISPCNT 10 次，
 若值在变 ⇒ 说明读的时刻处在 VBlank/HBlank 边界，读到的是过渡值。

用法：python scripts/research/firered/61_verify_io_read.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "ioverify"
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
local done_probe = false

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f

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

    -- 读档后稳定 200 帧再探针
    if proved and frame > 900 and (not done_probe) then
        done_probe = true

        -- ① readRange 一次读 0x60
        local rng = emu:readRange(0x04000000, 0x60)
        local hex = {}
        for i = 1, #rng do hex[#hex+1] = string.format("%02X", rng:byte(i)) end
        RL("[RANGE] " .. table.concat(hex, " "))

        -- ② read16 逐寄存器读
        local names = {0x00,0x02,0x04,0x06,0x08,0x0A,0x0C,0x0E,
                       0x10,0x12,0x14,0x16,0x18,0x1A,0x1C,0x1E}
        local r16 = {}
        for _, off in ipairs(names) do
            local ok, v = pcall(function() return emu:read16(0x04000000 + off) end)
            r16[#r16+1] = string.format("%02X=%s", off,
                ok and string.format("%04X", v) or "ERR")
        end
        RL("[READ16] " .. table.concat(r16, " "))

        -- ③ 连续读 DISPCNT 10 次（看是否在变）
        local ds = {}
        for i = 1, 10 do
            local ok, v = pcall(function() return emu:read16(0x04000000) end)
            ds[#ds+1] = ok and string.format("%04X", v) or "ERR"
        end
        RL("[DISPCNT x10] " .. table.concat(ds, " "))

        -- ④ 也读一下 0x03000000（IWRAM）开头，确认 readRange 本身对不对
        local iw = emu:readRange(0x03000000, 0x10)
        local ih = {}
        for i = 1, #iw do ih[#ih+1] = string.format("%02X", iw:byte(i)) end
        RL("[IWRAM] " .. table.concat(ih, " "))

        -- ⑤ 用 read32 读 0x0400000
        local ok32, v32 = pcall(function() return emu:read32(0x04000000) end)
        RL("[READ32@0x04000000] " .. (ok32 and string.format("%08X", v32) or "ERR"))

        DS_DONE(0, "probed")
    end

    if frame > 3000 then DS_DONE(1, "timeout") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=900,
                rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- _run.log ---")
    print(r.log_text)
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
