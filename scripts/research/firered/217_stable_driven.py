"""调研(217) 正确判据：等画面稳定再操作，不用内存内存判据。

═══ 216 的根本问题 ═══
s01_prove 是**全白画面**（507 字节 PNG）。PROVE 在 f=510 触发时，
游戏还在白屏加载阶段 —— 那时 EWRAM 里已经有存档数据，但画面还没出来。

⇒ 「EWRAM 出现 IDENT」这个判据**太早**，不可用于确认"已进入菜单"。

正确判据：**VRAM 画面连续 N 帧不变 = 画面已稳定**。
用这个判据，不管当前是什么界面，都能可靠地知道"可以按键了"。

本脚本：完全不用 IDENT，只用「画面稳定」驱动。
 ① 等画面稳定（连续 60 帧 VRAM 前 0x4000 不变）
 ② 遇稳定就截图，然后按 A
 ③ 重复 12 次，形成完整时间线

这样能看清：标题 → 存档菜单 → 冒险回顾 → 地图，每一步都截到。

用法：python scripts/research/firered/217_stable_driven.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party217"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local HOLDN = 18
local hold, wait = 0, 0
local shot = 0
local lastv, stable = nil, 0
local acted = 0
local MAXACT = 14

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
    RL("[SNAP] " .. n .. " " .. tag .. " f=" .. RUN.f .. " act=" .. acted)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    -- 只等画面稳定
    local v = rd(0x06000000, 0x4000)
    if v and lastv and v == lastv then
        stable = stable + 1
    else
        stable = 0
    end
    lastv = v

    if stable >= 60 then
        -- 画面稳定了，记录并操作
        acted = acted + 1
        if acted > MAXACT then
            RL("[DONE] acted=" .. acted)
            DS_DONE(0, "done")
            return
        end
        snap("stable" .. string.format("%02d", acted))
        stable = 0
        if acted == 1 then
            -- 标题：按 START 进入
            hold = HOLDN; setk(START)
            RL("[ACT1] START at title")
        elseif acted <= 6 then
            -- 存档菜单/回顾：按 A 继续
            hold = HOLDN; setk(A)
            RL("[ACT" .. acted .. "] A")
        else
            -- 地图：按 START 开菜单
            hold = HOLDN; setk(START)
            RL("[ACT" .. acted .. "] START (menu)")
        end
        return
    end

    if f > 22000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_stable01.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图（sha 前 8 位）：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<30} {h}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
