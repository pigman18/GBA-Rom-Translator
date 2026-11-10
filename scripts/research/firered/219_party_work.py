"""调研(219) 最终版：到冒险回顾就狂按 B，然后 START 开菜单进队伍。

═══ 218 揭示的完整流程 ═══
s01-s02 (2172f4e3)  白屏
s03      (7f005cbb) 标题出现中
s04      (b9a8c032) 标题
s05      (a344eb8b) 标题
s06      (d9164daa) 标题
s07..s13            存档菜单相关画面（A 反复推进）
s14      (98890da0) 「继续游戏」菜单
s15      (47fbde60) 黑屏（切换中）
s16      (198b6d4f) ★「冒险回顾 3」画面 ← 正是用户说的那个

【本脚本策略】
不再按序号硬编码，改用**画面指纹**判断：
  · 检测到「冒险回顾」（通过 VRAM 里出现特定 tile 模式或直接按计划）
  
更简单可靠：用「阶段 + 该阶段该按的键」：
  phase=title   : 按 A，直到画面变成存档菜单
  phase=menu    : 按 A（选继续游戏）
  phase=recap   : 狂按 B（每 8 帧一次，60 次）
  phase=map     : 按 START 开菜单
  phase=game_menu: 按 A 进队伍
  
判据「进入回顾」：画面出现大块非白/非标题特征 -> 用「连续 3 帧画面都在变」
                 （回顾有动画）
判据「回到地图」：按 B 之后画面稳定且不再变化

用法：python scripts/research/firered/219_party_work.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party219"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local HOLDN = 18
local hold, wait = 0, 0
local shot = 0
local lastv, stable = nil, 0
local shotn = 0

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

-- 主状态机
local phase = "title"
local a_cnt, b_cnt = 0, 0

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    local v = rd(0x06000000, 0x4000)
    if v and lastv and v == lastv then stable = stable + 1
    else stable = 0 end
    lastv = v

    if phase == "title" then
        if stable >= 50 then
            a_cnt = a_cnt + 1
            stable = 0
            snap("title" .. string.format("%02d", a_cnt))
            if a_cnt >= 8 then
                phase = "recap"
                b_cnt = 0
                RL("[PHASE] title->recap after " .. a_cnt .. " A")
                return
            end
            hold = HOLDN; setk(A)
            RL("[TITLE-A] " .. a_cnt)
        end
        return
    end

    if phase == "recap" then
        b_cnt = b_cnt + 1
        if b_cnt == 1 then
            snap("recap_start")
        end
        if b_cnt >= 70 then
            RL("[PHASE] recap done, b=" .. b_cnt)
            snap("recap_end")
            phase = "map"
            wait = 50
            return
        end
        setk(B); hold = 8
        if b_cnt % 20 == 0 then
            RL("[RECAP-B] " .. b_cnt)
        end
        return
    end

    if phase == "map" then
        if stable >= 40 then
            stable = 0
            snap("map")
            RL("[PHASE] map stable -> START")
            phase = "gm"
            hold = HOLDN; setk(START)
            wait = 80
        end
        return
    end

    if phase == "gm" then
        snap("game_menu")
        RL("[PHASE] menu -> A for party")
        phase = "pty"
        hold = HOLDN; setk(A)
        wait = 130
        return
    end

    if phase == "pty" then
        snap("party")
        RL("[DONE]")
        DS_DONE(0, "done")
    end

    if f > 24000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_title01.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-3500:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<30} {h}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
