"""调研(261) 进队伍界面精确 dump，然后穷举所有解码组合定死小字格式。

═══ 为什么再做一次 ═══
之前 232 的 party232 快照虽然进了队伍界面，但我在解码时反复试错
（swap/noshift、8x8/8x16），始终没和 VRAM 里的小字 tile 对上。

本脚本：
 ① 用已跑通的路线进队伍界面（228/232 验证过）：
      标题 0x9F40 -> A -> 继续游戏 0x3140 -> UP -> A
      -> 冒险回顾 0x7F60 -> B×11 -> 野外
      -> START -> DOWN(16帧) -> A -> 队伍 0x1740
 ② 在队伍界面**连拍 5 帧**（间隔 20 帧），每次全量 dump
    （避免单帧状态不定）
 ③ 记录每帧的 DISPCNT，确认都在 0x1740

产出给 (262) 做穷举。

用法：python scripts/research/firered/261_party_dump.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party261"

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

local shotn = 0
local function dump(tag)
    shotn = shotn + 1
    local i = string.format("%02d", shotn)
    local dc = rd16(0x04000000)
    emu:screenshot(OUTP .. "/s" .. i .. "_" .. tag .. ".png")
    for _, sp in ipairs({
        { "vram", 0x06000000, 0x18000 },
        { "ewram", 0x02000000, 0x40000 },
        { "iwram", 0x03000000, 0x8000 },
        { "pal", 0x05000000, 0x400 },
    }) do
        local d = rd(sp[2], sp[3])
        if d then wr("s" .. i .. "_" .. tag .. "_" .. sp[1] .. ".bin", d) end
    end
    RL(string.format("[DUMP] %02d %-14s dc=0x%04X f=%d", shotn, tag, dc, RUN.f))
end

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local bn, dn = 0, 0
local sn = 0

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
        if dc_is(0x9F40, 10) then
            phase = "a1"; hold = 16; setk(K.A); return
        end
        if f > 8000 then DS_DONE(1, "no-title") end
        return
    end
    if phase == "a1" then phase = "await_menu"; return end
    if phase == "await_menu" then
        if dc_is(0x3140, 8) then
            phase = "up"; hold = 10; setk(K.UP); wait = 25; return
        end
        if f > 12000 then DS_DONE(1, "no-menu") end
        return
    end
    if phase == "up" then
        phase = "a2"; hold = 16; setk(K.A); wait = 80; return
    end
    if phase == "a2" then
        if dc_is(0x7F60, 20) then phase = "press_b"; bn = 0; return end
        if f > 16000 then DS_DONE(1, "no-recap") end
        return
    end
    if phase == "press_b" then
        bn = bn + 1
        if bn > 11 then
            phase = "open"; hold = 16; setk(K.START); wait = 90
            return
        end
        setk(K.B); hold = 10; wait = 40
        return
    end
    if phase == "open" then
        phase = "down"; hold = 16; setk(K.DOWN); wait = 40
        return
    end
    if phase == "down" then
        phase = "enter"; hold = 16; setk(K.A); wait = 220
        return
    end
    if phase == "enter" then
        -- 到了队伍界面：连拍 5 帧
        phase = "burst"; sn = 0; wait = 10
        return
    end
    if phase == "burst" then
        sn = sn + 1
        dump("party" .. string.format("%02d", sn))
        if sn >= 5 then
            DS_DONE(0, "dumped")
            return
        end
        wait = 20
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
    r = run_lua(LUA, OUT, expect_files=["s01_party01_vram.bin"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-2000:])
    print("\n产出：")
    for s in sorted(OUT.glob("s*_party*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<30} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
