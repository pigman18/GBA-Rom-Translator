"""调研(224) 用 _lib.lua 的状态驱动方式进队伍，并实测火红各界面的 DISPCNT。

═══ 找到的现成资产（我此前完全忽略）═══
bot/scenes/POKEMON_RUBY_AXVJ00/_lib.lua  17KB 通用场景库，已解决：
  · boot_and_load : await(dispcnt) 等标题 → tap A → await(菜单或野外) → wait
  · open_menu_at  : START → UP×8 → DOWN×(index-1)
  · prove         : EWRAM 搜存档身份字节
  · burst/shot    : 连续帧采集

且注释明确写着踩过的坑（我正好全踩了）：
  ⚠ 读档序列里**不能夹 B**（B 会把「继续游戏」确认取消，退回标题）
  ⚠ 标题画面本身是静止的，纯 settle 会停在错的地方 → 必须 await(dispcnt)

═══ 已实测到的火红特征 ═══
  「继续游戏」菜单：DISPCNT = 0x3140   （与 ruby 相同）
  标题画面：待测

本脚本：按 _lib.lua 的顺序做，但**慢慢推进并记录每步的 DISPCNT**，
先拿到火红的特征值，再决定 await 用哪个数。

用法：python scripts/research/firered/224_dispcnt_map.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "disp224"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local hold, wait = 0, 0
local lastv, stable = nil, 0
local shotn = 0
local stepn = 0

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
local function wr(n, d)
    local f = assert(io.open(OUTP .. "/" .. n, "wb"))
    f:write(d); f:close()
end
local function snap(tag)
    shotn = shotn + 1
    local n = string.format("%02d", shotn)
    local dc = rd16(0x04000000)
    local bg0 = rd16(0x04000008)
    emu:screenshot(OUTP .. "/s" .. n .. "_" .. tag .. ".png")
    RL(string.format("[SNAP] %02d %-16s dispcnt=0x%04X bg0=0x%04X f=%d",
                     shotn, tag, dc, bg0, RUN.f))
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    local v = rd(0x06000000, 0x4000)
    if v and lastv and v == lastv then stable = stable + 1 else stable = 0 end
    lastv = v

    -- 每次画面稳定就记录一次特征并推进
    if stable >= 50 then
        stable = 0
        stepn = stepn + 1
        snap("st" .. string.format("%02d", stepn))

        if stepn > 14 then
            RL("[DONE]")
            DS_DONE(0, "done")
            return
        end

        -- 按 _lib.lua 的顺序：先 A 进标题/菜单，绝不在读档序列里按 B
        if stepn <= 9 then
            hold = 16; setk(A)
            RL("[A] step " .. stepn)
        elseif stepn <= 12 then
            hold = 16; setk(START)
            RL("[START] step " .. stepn)
        else
            hold = 16; setk(A)
            RL("[A] step " .. stepn)
        end
        return
    end

    if f > 30000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_st01.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=520)
    print(r.report())
    print(r.log_text[-2500:])
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
