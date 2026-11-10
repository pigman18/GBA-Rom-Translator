"""调研(222) 关键实验：在冒险回顾画面里，A 和 B 各按一次，看效果差异。

═══ 221 的观察 ═══
s11/s12 都是「冒险回顾 1」（两个不同 sha，说明有细微变化但页号没变）
⇒ A 在这一页上翻不动。

用户说「狂按 B 退出」。之前 219 按 B 退回标题，但那时是在**白屏/加载中**按的。

本脚本做对照实验：
 ① 一直按 A 直到出现回顾画面（检测：tilemap 里出现"冒险回顾"那类文字）
 ② 到达后暂停，截图
 ③ 按 B 一次，等 40 帧，截图
 ④ 再按 B 一次，等 40 帧，截图
 ⑤ 再按 A 一次，等 40 帧，截图

这样能直接看出哪种键能退出回顾。

用法：python scripts/research/firered/222_ab_test.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party222"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local HOLDN = 16
local hold, wait = 0, 0
local shotn = 0
local lastv, stable = nil, 0
local acnt = 0
local phase = "push_a"
local bstep = 0

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
            if acnt >= 12 then
                RL("[PHASE] now test keys")
                phase = "testB"
                bstep = 0
                return
            end
            hold = HOLDN; setk(A)
            RL("[A] " .. acnt)
            return
        end

        if phase == "testB" then
            bstep = bstep + 1
            if bstep > 4 then
                RL("[TEST-DONE]")
                DS_DONE(0, "tested")
                return
            end
            snap("B" .. bstep)
            hold = HOLDN; setk(B)
            RL("[TEST-B] step=" .. bstep)
            wait = 40
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
    print(r.log_text[-2500:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<26} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
