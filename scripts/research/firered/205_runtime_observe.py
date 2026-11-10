"""调研(205) 用 Lua 观察运行时的字形组装过程。

═══════════════════════════════════════════════════════════════════════════
【已确证的事实（本轮 176-204）】
═══════════════════════════════════════════════════════════════════════════
F1 汉字 12px 宽 x 16px 高，pitch 13px（197 实测）
F2 取字形函数 0x081DB3EE：
     页表 @0x08B74000（11 项）→ 页基址
     offset = (lo>>3)*512 + (lo&7)*32
F3 EWRAM 0x02000E30 起有解码缓冲：7 个 32B 块，值域全是 {10,11,12}
   之后全 aa（背景）—— 这是**当前屏已解码的字形**
F4 IWRAM 0x03003DE0 也是同类缓冲（值域 {A,B,C}）
F5 VRAM tile1..7 = EWRAM 0x02000E30..0x02000EF0（逐字节相同）

【关键疑问：一个 tile 只有 8px 宽，怎么出 12px 字？】
两种可能：
  M1 横向拼接：字宽 12 = tile[0..7] + 下一 tile 的左 4px
  M2 字库本身按 12 宽存，解压时拆成 2 个 tile 送 VRAM

【本脚本：用 Lua 在运行时采样，回答 M1/M2】
 ① 读档进中文菜单
 ② 每帧（或每 N 帧）dump：
      - EWRAM 0x02000E00..0x02001200（解码缓冲）
      - VRAM 0x06000000..0x06002000（charBase 前 256 tile）
      - IWRAM 0x03003D00..0x03004000
 ③ 按帧对比，找出「哪个地址先出现新字形、何时被搬到 VRAM」
 ④ 同时记录按键，标记画面切换时刻

【输出】
 work/_probe/runtime205/frame_NNN_{ewram,vram,iwram}.bin
 work/_probe/runtime205/timeline.json   每帧的摘要与变化点

【单次启动纪律】
 - STARTUPINFO+SW_HIDE，不起 150ms 轮询隐藏线程（避免闪屏）
 - 只启动一次
 - Lua 自己能正常退出（DS_DONE），不依赖 GDB
 - 不用 GDB（178 教训：断点会冻结整个模拟器）

用法：python scripts/research/firered/205_runtime_observe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "runtime205"

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
local saved = 0
local last_ew = nil
local last_vr = nil
local tick = 0

local function setk(m) emu:setKeys(m) end

local function dump(name, addr, len)
    local ok, b = pcall(function() return emu:readRange(addr, len) end)
    if not ok or not b then return nil end
    local f = assert(io.open(OUTP .. "/" .. name, "wb"))
    f:write(b); f:close()
    return b
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0) end
        return
    end

    -- 读档检测
    if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] f=" .. f)
            -- 读档瞬间采样
            dump("t000_prove_ewram.bin", 0x02000000, 0x40000)
            dump("t000_prove_vram.bin", 0x06000000, 0x18000)
            dump("t000_prove_iwram.bin", 0x03000000, 0x8000)
            dump("t000_prove_pal.bin", 0x05000000, 0x400)
            emu:screenshot(OUTP .. "/t000_prove.png")
            saved = saved + 1
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

    -- 读档后：定时采样，同时按 A/B 触发画面变化
    tick = tick + 1

    -- 每次按键前后各采样一次，便于对比
    local r = tick % 120
    if r == 1 then
        if saved < 40 then
            local tag = string.format("%03d", saved)
            dump("t" .. tag .. "_a_ewram.bin", 0x02000C00, 0x800)
            dump("t" .. tag .. "_a_vram.bin", 0x06000000, 0x4000)
            dump("t" .. tag .. "_a_iwram.bin", 0x03003C00, 0x800)
            saved = saved + 1
        end
        setk(A); hold = 8
        RL("[A] f=" .. f .. " tick=" .. tick)
    elseif r == 40 then
        if saved < 40 then
            local tag = string.format("%03d", saved)
            dump("t" .. tag .. "_b_ewram.bin", 0x02000C00, 0x800)
            dump("t" .. tag .. "_b_vram.bin", 0x06000000, 0x4000)
            dump("t" .. tag .. "_b_iwram.bin", 0x03003C00, 0x800)
            saved = saved + 1
        end
        setk(B); hold = 8
        RL("[B] f=" .. f .. " tick=" .. tick)
    end

    if tick > 1200 then
        RL("[DONE-SAMPLES] " .. saved)
        DS_DONE(0, "sampled")
    end
    if f > 8000 then DS_DONE(1, "late") end
end))
'''

EXPECT = ["t000_prove_ewram.bin", "t000_prove_vram.bin", "t000_prove.png"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    ident = SAVE_FR.read_bytes()[:8].hex()
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=420,
                extra_env={"EMU_IDENT": ident})
    print(r.report())
    print(r.log_text)
    if not r.ok:
        print("! 运行未通过三层校验")
        return 1
    files = sorted(OUT.glob("*.bin"))
    print(f"\n产出 {len(files)} 个 bin")
    for f in files[:12]:
        print(f"  {f.name:<30} {f.stat().st_size:>8,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
