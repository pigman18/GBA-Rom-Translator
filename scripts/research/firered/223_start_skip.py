"""调研(223) 用 START 跳过冒险回顾（而不是 A/B）。

═══ 前面 8 次失败的模式总结 ═══
A：翻页/推进，但在回顾里翻不动
B：219 退回标题（加载中按），222 只是让回顾继续播

火红过场动画的标准跳过键通常是 **START** 或 **B**。
既然 B 无效，试 START。

本脚本：
 ① 先按 A 到出现回顾画面（约 11 次）
 ② 然后按 START 数次，看是否跳过
 ③ 每步截图

用法：python scripts/research/firered/223_start_skip.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party223"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local HOLDN = 16
local hold, wait = 0, 0
local shotn = 0
local lastv, stable = nil, 0
local acnt = 0
local phase = "push_a"
local sstep = 0

local function setk(m) emu:setKeys(m) end
local function rd(a, l)
    local ok, b = pcall(function() return emu:readRange(a, l) end)
    if ok and b then return b end
    return nil
end
local function wr(n, d)
    local f = assert(io.open(OUTP .. "/" .. n, "wb"))
    f:write(d); f:close()
end
local function snap(tag)
    shotn = shotn + 1
    local n = string.format("%02d", shotn)
    local v = rd(0x06000000, 0x18000)
    if v then wr("s" .. n .. "_" .. tag .. "_vram.bin", v) end
    local e = rd(0x02000000, 0x40000)
    if e then wr("s" .. n .. "_" .. tag .. "_ewram.bin", e) end
    local i = rd(0x03000000, 0x8000)
    if i then wr("s" .. n .. "_" .. tag .. "_iwram.bin", i) end
    emu:screenshot(OUTP .. "/s" .. n .. "_" .. tag .. ".png")
    RL("[SNAP] " .. n .. " " .. tag .. " f=" .. RUN.f)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    local v = rd(0x06000000, 0x4000)
    if v and lastv and v == lastv then stable = stable + 1 else stable = 0 end
    lastv = v

    if stable >= 45 then
        stable = 0

        if phase == "push_a" then
            acnt = acnt + 1
            snap("a" .. string.format("%02d", acnt))
            if acnt >= 11 then
                RL("[PHASE] recap reached, try START")
                phase = "testSTART"
                sstep = 0
                return
            end
            hold = HOLDN; setk(A)
            RL("[A] " .. acnt)
            return
        end

        if phase == "testSTART" then
            sstep = sstep + 1
            if sstep > 4 then
                RL("[TEST-DONE]")
                DS_DONE(0, "tested")
                return
            end
            snap("START" .. sstep)
            hold = HOLDN; setk(START)
            RL("[TEST-START] step=" .. sstep)
            wait = 50
            return
        end
    end

    if f > 60000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_a01.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=600)
    print(r.report())
    print(r.log_text[-2000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<26} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
