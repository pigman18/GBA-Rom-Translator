"""调研(218) 修正按键序列：标题按 A，存档菜单按 A，回顾按 B，地图按 START。

═══ 217 揭示的真实流程 ═══
s01-s02 (2172f4e3)  白屏加载
s03      (d0cf1259) 标题前段
s04      (d5e37d2d) 标题
s05      (578fdb8b) 标题
s06      (92e05787) 标题画面「PUSH START BUTTON」
  -- 按 A --
s07..s14 (98890da0) 「继续游戏」菜单  ← 卡在这里，因为我在按 START

结论：**标题画面按 A 就行，不需要 START**。进了存档菜单也按 A。

新序列（按画面指纹判断，不再按序号硬编码）：
  指纹 A (标题) -> 按 A
  指纹 B (存档菜单) -> 按 A（继续游戏）
  进入回顾 -> 狂按 B
  地图 -> START

简化实现：统一先按 A，如果连续 3 次按 A 画面都不变，改按 B，
再不变就按 START。

用法：python scripts/research/firered/218_party_final.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party218"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local HOLDN = 18
local hold, wait = 0, 0
local shot = 0
local lastv, stable = nil, 0
local acted = 0
local nochange = 0
local keyplan = {A, A, A, A, B, B, B, B, B, B, START, A, A, A, A, A}
local plani = 0

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
    shot = shot + 1
    local n = string.format("%02d", shot)
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
    if v and lastv and v == lastv then stable = stable + 1
    else stable = 0 end
    lastv = v

    if stable >= 55 then
        acted = acted + 1
        if plani >= #keyplan or acted > 24 then
            RL("[DONE] acted=" .. acted)
            DS_DONE(0, "done")
            return
        end
        plani = plani + 1
        local k = keyplan[plani]
        snap("a" .. string.format("%02d", acted))
        stable = 0
        hold = HOLDN
        setk(k)
        local kn = (k == A) and "A" or ((k == B) and "B" or "START")
        RL("[ACT" .. acted .. "] key=" .. kn .. " plani=" .. plani)
        return
    end

    if f > 24000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_a01.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-3500:])
    print("\n截图（sha 前 8 位）：")
    seen = {}
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        tag = seen.get(h, "")
        seen[h] = h
        print(f"  {s.name:<28} {h} {tag}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
