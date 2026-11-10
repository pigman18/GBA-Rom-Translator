"""调研(295) 抓队伍界面正在绘制的字形 —— 直接判定字号。

═══ 为什么这一步能定论 ═══
0x03003DE0 是**字形解码输出缓冲**（0x081DB3EE 写它），
0x03003E60 存宽/高（strb 宽, strb 高）。

队伍界面渲染时，每画一个字就把该字的位图解码到 0x03003DE0，
并把宽高写到 0x03003E60。

⇒ 在队伍界面高频采样这两处：
   · 得到的 128B 位图 = 屏幕上真实正在画的字形
   · 0x03003E60 的 2 字节 = 该字的宽/高
   · 宽=8 就是小字，宽=0x0A/0x0C 就是大字
这是**最直接的证据**，不依赖任何静态推断。

路线（228~232 已跑通）：
  标题0x9F40 -A-> 继续游戏0x3140 -UP,A-> 冒险回顾0x7F60 -Bx11->
  野外 -> START -> DOWN -> A -> 队伍0x1740

用法：python scripts/research/firered/295_catch_glyph_live.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "glyphs295"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local K = { A = 1, B = 2, START = 8, UP = 64, DOWN = 128 }

local function setk(m) emu:setKeys(m) end
local function rd(a, l)
    local ok, b = pcall(function() return emu:readRange(a, l) end)
    if ok and b then return b end
    return nil
end
local function rd16(a)
    local ok, v = pcall(function() return emu:read16(a) end)
    if ok then return v end
    return 0
end
local function wr(nm, d)
    local f = assert(io.open(OUTP .. "/" .. nm, "wb"))
    f:write(d); f:close()
end

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local bn, sn = 0, 0
local recs = {}
local MAXREC = 400

local function dc_is(want, k)
    local dc = rd16(0x04000000)
    if dc == want then dc_n = dc_n + 1 else dc_n = 0 end
    return dc_n >= (k or 8)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    if phase == "await_title" then
        if dc_is(0x9F40, 10) then phase = "a1"; hold = 16; setk(K.A); return end
        if f > 8000 then DS_DONE(1, "no-title") end
        return
    end
    if phase == "a1" then phase = "await_menu"; return end
    if phase == "await_menu" then
        if dc_is(0x3140, 8) then phase = "up"; hold = 10; setk(K.UP); wait = 25; return end
        if f > 12000 then DS_DONE(1, "no-menu") end
        return
    end
    if phase == "up" then phase = "a2"; hold = 16; setk(K.A); wait = 80; return end
    if phase == "a2" then
        if dc_is(0x7F60, 20) then phase = "press_b"; bn = 0; return end
        if f > 16000 then DS_DONE(1, "no-recap") end
        return
    end
    if phase == "press_b" then
        bn = bn + 1
        if bn > 11 then phase = "open"; hold = 16; setk(K.START); wait = 90; return end
        setk(K.B); hold = 10; wait = 40
        return
    end
    if phase == "open" then phase = "down"; hold = 16; setk(K.DOWN); wait = 40; return end
    if phase == "down" then phase = "enter"; hold = 16; setk(K.A); wait = 220; return end
    if phase == "enter" then
        -- 到队伍界面，开始采样
        RL("[PARTY] dc=0x" .. string.format("%04X", rd16(0x04000000)))
        phase = "sample"
        wait = 10
        return
    end

    if phase == "sample" then
        local buf = rd(0x03003DE0, 128)
        local wh = rd(0x03003E60, 2)
        if buf and wh and #buf == 128 and #wh == 2 then
            recs[#recs + 1] = buf .. wh
            sn = sn + 1
        end
        if sn >= MAXREC then
            wr("samples.bin", table.concat(recs))
            RL("[SAMPLED] " .. sn)
            DS_DONE(0, "sampled")
            return
        end
        return
    end

    if f > 40000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["samples.bin"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-1500:])
    p = OUT / "samples.bin"
    if p.exists():
        data = p.read_bytes()
        n = len(data) // 130
        print(f"\n采样 {n} 条（每条 128B 位图 + 2B 宽高）")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
