"""调研(297) 修正采样方法：在「重绘发生」时抓宽高，验证是否存在 8 宽字体。

═══ 295 的方法缺陷 ═══
我连续采了 400 帧，得到 400 条**完全相同**的记录（宽12 高13、1 种位图）。
这不是"队伍界面只有一种字号"，而是**这 400 帧内屏幕根本没重绘** ——
0x03003DE0 里是上一次绘制留下的静态结果。

═══ 回看反汇编（关键）═══
所有字体函数的宽高都写到**同一对地址**：
    0x081DB3EE: ldr r1,[pc]=0x03003E60; strb 宽,[r1]; strb 高,[r1,#1]
    0x080062B4: r5=0x03003DE0; r1=r5+0x80(=0x03003E60) strb 宽=8
                               r5=r5+0x81(=0x03003E61) strb 高=0x0C
   0x08006354: 同 0x03003E60
   ...
⇒ 0x03003E60/61 是「最后一次绘制的字」的宽高。

⇒ 要统计「用过哪些字号」，必须**在重绘发生时采样**，并记录每一次变化。

本脚本：
 ① 进队伍界面
 ② 按 UP/DOWN 反复移动光标（每次移动都会重绘名字）
 ③ **每帧**采样 0x03003DE0 与 0x03003E60
 ④ 只记录「位图或宽高发生变化」的时刻
 ⑤ 统计出现过的所有 (宽,高) 组合

用法：python scripts/research/firered/297_sample_on_repaint.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "repaint297"

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
local bn = 0
local last_buf, last_wh = nil, nil
local changes = {}      -- 每条: 128B 位图 + 2B 宽高
local nchg = 0
local pressed = 0

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
        RL("[PARTY] dc=0x" .. string.format("%04X", rd16(0x04000000)))
        phase = "watch"
        return
    end

    -- 阶段 watch：每帧比对，只记变化；同时周期性按键触发重绘
    if phase == "watch" then
        local buf = rd(0x03003DE0, 128)
        local wh = rd(0x03003E60, 2)
        if buf and wh and #buf == 128 and #wh == 2 then
            local changed = false
            if last_buf == nil then
                changed = true
            elseif buf ~= last_buf or wh ~= last_wh then
                changed = true
            end
            if changed and nchg < 600 then
                nchg = nchg + 1
                changes[#changes + 1] = buf .. wh
            end
            last_buf, last_wh = buf, wh
        end

        -- 每 8 帧按一次方向键（触发重绘），方向在 UP/DOWN 间交替
        if f % 8 == 0 then
            pressed = pressed + 1
            if pressed % 2 == 1 then
                setk(K.DOWN); hold = 3
            else
                setk(K.UP); hold = 3
            end
        end

        if nchg >= 600 or f > 34000 then
            wr("changes.bin", table.concat(changes))
            RL("[CHANGES] n=" .. nchg .. " pressed=" .. pressed)
            DS_DONE(0, "done")
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
    r = run_lua(LUA, OUT, expect_files=["changes.bin"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-1500:])
    p = OUT / "changes.bin"
    if p.exists():
        print(f"\n变化记录 {len(p.read_bytes()) // 130} 条")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
