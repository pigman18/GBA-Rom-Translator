"""调研(206) 高密度采样：抓 IWRAM 0x03003DE0 缓冲区被写入的瞬间。

═══════════════════════════════════════════════════════════════════════════
【已确证的数据流（205 + 离线分析）】
═══════════════════════════════════════════════════════════════════════════
  ROM 字库源(未知) → 解码 → IWRAM 0x03003DE0 → EWRAM 0x02000E30 → VRAM
                                  (值域 A/B/C)      (6行x24字x32B)

  证据：
   · VRAM tile1..7 == EWRAM 0x02000E30 + 32k  （20/20 全match）
   · EWRAM 缓冲布局 = 6 行 x 24 字 x 32B，行距 0x300
   · IWRAM 0x03003DE0 值域 {A,B,C}，与 EWRAM 的 {10,11,12} 同构
   · 144 个字去 ROM 查：0 命中（含墨迹掩码）

【本脚本目标】
 抓「IWRAM 0x03003DE0 从全 A 变成有墨」的那一帧，然后在同一帧
 记录 IWRAM 全量 + EWRAM 全量，从中找：
   · 是否有中间缓冲（另一个 IWRAM/EWRAM 区域先出现该字形）
   · 是否有 ROM 指针（0x08xxxxxx）紧邻这些数据

【采样策略：高频 + 变化检测】
 每帧读 IWRAM 0x03003D00..0x03004100（1KB），
 与上一帧比较，只要有变化就记录（最多 300 次），
 从而抓到「写入过程」而不只是「写完后」。

【不使用 GDB】（178 教训：断点会冻结整个模拟器）

用法：python scripts/research/firered/206_catch_write.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "catch206"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A, B = 1, 2
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
local tick = 0
local last1, last2, last3 = nil, nil, nil
local saved = 0

local function setk(m) emu:setKeys(m) end
local function rd(a, n)
    local ok, b = pcall(function() return emu:readRange(a, n) end)
    if ok and b then return b end
    return nil
end
local function wr(name, data)
    local f = assert(io.open(OUTP .. "/" .. name, "wb"))
    f:write(data); f:close()
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0) end
        return
    end

    if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
        local ew = rd(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] f=" .. f)
            wr("t000_prove_ewram.bin", ew)
            wr("t000_prove_iwram.bin", rd(0x03000000, 0x8000))
            wr("t000_prove_vram.bin", rd(0x06000000, 0x18000))
        end
    end

    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1
        else last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true
            hold = 12
            setk(A)
        end
        if f > 6000 then DS_DONE(1, "no-save") end
        return
    end

    tick = tick + 1

    -- 每帧读三块，检测变化
    local b1 = rd(0x03003D00, 0x400)
    local b2 = rd(0x02000E00, 0x400)
    local b3 = rd(0x02001100, 0x400)
    if b1 and b2 and b3 then
        local changed = false
        if last1 == nil then
            changed = true
        elseif b1 ~= last1 or b2 ~= last2 or b3 ~= last3 then
            changed = true
        end
        if changed and saved < 400 then
            local tag = string.format("%04d", saved)
            wr("f" .. tag .. "_iw.bin", b1)
            wr("f" .. tag .. "_ew0.bin", b2)
            wr("f" .. tag .. "_ew1.bin", b3)
            saved = saved + 1
        end
        last1, last2, last3 = b1, b2, b3
    end

    -- 每 150 帧按一次键，制造画面变化
    local r = tick % 150
    if r == 1 then
        setk(A); hold = 8
        RL("[A] f=" .. f)
    elseif r == 75 then
        setk(B); hold = 8
        RL("[B] f=" .. f)
    end

    if saved >= 400 then
        RL("[DONE-SAMPLES] " .. saved)
        DS_DONE(0, "full")
    end
    if tick > 1500 then
        RL("[DONE-SAMPLES] " .. saved)
        DS_DONE(0, "timeout-samples")
    end
    if f > 9000 then DS_DONE(1, "late") end
end))
'''

EXPECT = ["t000_prove_iwram.bin"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=420,
                extra_env={"EMU_IDENT": SAVE_FR.read_bytes()[:8].hex()})
    print(r.report())
    print(r.log_text[-1500:])
    if not r.ok:
        return 1
    n = len(list(OUT.glob("f*_iw.bin")))
    print(f"\n采样 {n} 帧")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
