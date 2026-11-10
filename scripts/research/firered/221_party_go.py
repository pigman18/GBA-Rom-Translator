"""调研(221) 一直按 A 翻完冒险回顾，进入地图，START 开菜单，进队伍。

═══ 220 证实 ═══
s10 = 冒险回顾 3
s11 = 冒险回顾 1
⇒ **A 在回顾里是翻页**，能翻完并进入游戏。

220 失败是因为 has_content 判据把某些画面当成"未就绪"，
以及 f>24000 上限太紧。

本脚本：
 ① 不设 has_content 判据，只用「画面稳定 40 帧」
 ② A 按到地图出现（判据：DISPCNT 的 OBJ 位 = 1 且画面稳定）
 ③ 地图上按 START 开菜单，截图
 ④ 菜单里按 A 进队伍，截图 + dump

按键序列：先 12 次 A（翻完标题+回顾），然后 START，再 A。

用法：python scripts/research/firered/221_party_go.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party221"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local HOLDN = 16
local hold, wait = 0, 0
local shotn = 0
local lastv, stable = nil, 0
local phase = "push_a"
local acnt = 0
local MAXA = 16

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
            if acnt > MAXA then
                RL("[PHASE] a done -> START")
                phase = "menu"
                hold = HOLDN; setk(START)
                wait = 90
                return
            end
            hold = HOLDN; setk(A)
            RL("[A] " .. acnt)
            return
        end

        if phase == "menu" then
            snap("game_menu")
            RL("[PHASE] menu -> A for party")
            phase = "party"
            hold = HOLDN; setk(A)
            wait = 130
            return
        end

        if phase == "party" then
            snap("party")
            RL("[DONE]")
            DS_DONE(0, "done")
            return
        end
    end

    -- 上限放大，避免提前退出
    if f > 40000 then DS_DONE(1, "late") end
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
    print(r.log_text[-3000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<26} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
