"""调研(225) 按 _lib.lua 的正确纪律进队伍：START → UP×8 → DOWN → A。

═══ 为什么这次不手搓 ═══
bot/scenes/POKEMON_RUBY_AXVJ00/_lib.lua 已解决全部时序问题，关键三条：
  ① 读档序列**绝不能夹 B**（会把「继续游戏」确认取消，退回标题）
  ② 标题画面本身静止，纯 settle 会停错地方 → 必须按 DISPCNT 判据 await
  ③ 开菜单统一：START → UP×8（保证到顶）→ DOWN×(index-1) → A
     不依赖进入时光标位置。

═══ 火红菜单顺序（7 项）═══
  1 图鉴 / 2 宝可梦 / 3 背包 / 4 训练家卡 / 5 存档 / 6 设置 / 7 关闭
  ⇒ 宝可梦 = index 2

═══ 已实测 ═══
  「继续游戏」菜单 DISPCNT = 0x3140

本脚本按状态机走，每步记录 DISPCNT，到队伍后 dump VRAM/EWRAM/IWRAM。

用法：python scripts/research/firered/225_party_lib.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party225"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START, UP, DOWN = 1, 2, 8, 64, 128
local hold, wait = 0, 0
local lastv, stable = nil, 0
local shotn = 0
local phase = "boot"
local n = 0

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
local function snap(tag, dump)
    shotn = shotn + 1
    local idx = string.format("%02d", shotn)
    local dc = rd16(0x04000000)
    local bg0 = rd16(0x04000008)
    emu:screenshot(OUTP .. "/s" .. idx .. "_" .. tag .. ".png")
    if dump then
        local v = rd(0x06000000, 0x18000)
        if v then wr("s" .. idx .. "_" .. tag .. "_vram.bin", v) end
        local e = rd(0x02000000, 0x40000)
        if e then wr("s" .. idx .. "_" .. tag .. "_ewram.bin", e) end
        local i = rd(0x03000000, 0x8000)
        if i then wr("s" .. idx .. "_" .. tag .. "_iwram.bin", i) end
        local p = rd(0x05000000, 0x400)
        if p then wr("s" .. idx .. "_" .. tag .. "_pal.bin", p) end
    end
    RL(string.format("[SNAP] %02d %-14s dispcnt=0x%04X bg0=0x%04X f=%d",
                     shotn, tag, dc, bg0, RUN.f))
end

-- 稳定判定：画面有内容且连续 K 帧不变
local function is_stable(v)
    if not v then return false end
    if v and lastv and v == lastv then stable = stable + 1 else stable = 0 end
    lastv = v
    return stable >= 45
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    local v = rd(0x06000000, 0x4000)
    local ok = is_stable(v)
    if not ok then
        if f > 40000 then DS_DONE(1, "late") end
        return
    end
    stable = 0

    -- ── 状态机 ──
    if phase == "boot" then
        snap("boot")
        -- 标题/版权：按 A 推进（不按 B！）
        phase = "boot_a"
        n = 0
        return
    end

    if phase == "boot_a" then
        n = n + 1
        snap("bootA" .. string.format("%02d", n))
        if n >= 8 then
            -- 8 次 A 后应该已进野外（_lib 的 boot 序列）
            phase = "to_map"
            wait = 200
            return
        end
        hold = 16; setk(A)
        return
    end

    if phase == "to_map" then
        snap("map_check", true)
        phase = "open_menu"
        -- _lib: START -> UP*8 -> DOWN*(index-1)
        hold = 16; setk(START)
        wait = 60
        return
    end

    if phase == "open_menu" then
        snap("menu_opening")
        -- 上移 8 次到顶
        for i = 1, 8 do setk(UP); end
        phase = "menu_up"
        n = 0
        return
    end

    if phase == "menu_up" then
        n = n + 1
        setk(UP); hold = 4
        wait = 8
        if n >= 8 then
            phase = "menu_down"
            n = 0
        end
        return
    end

    if phase == "menu_down" then
        n = n + 1
        setk(DOWN); hold = 4
        wait = 8
        if n >= 1 then
            phase = "menu_ready"
        end
        return
    end

    if phase == "menu_ready" then
        snap("menu_on_pokemon")
        phase = "enter"
        hold = 16; setk(A)
        wait = 120
        return
    end

    if phase == "enter" then
        snap("party_enter", true)
        phase = "party"
        wait = 60
        return
    end

    if phase == "party" then
        snap("party", true)
        RL("[PARTY-REACHED] f=" .. f)
        DS_DONE(0, "party")
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
    r = run_lua(LUA, OUT, expect_files=["s01_boot.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=520)
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图：")
    import hashlib
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<32} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
