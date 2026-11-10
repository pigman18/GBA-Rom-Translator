"""调研(232) 进队伍最后一步：菜单光标从「图鉴」下移到「宝可梦」。

═══ 231 的结果 ═══
s08 = 「宝可梦图鉴目录」← 说明 START 菜单打开了、A 也进去了，
      但光标停在**第 1 项「图鉴」**，我的 DOWN 没被识别（只按了 4 帧）。

⇒ 万事俱备，只差把 DOWN 按实。

本脚本：每一步都截图，DOWN 用 10 帧长按，并按 2 次（多按一次若已到
       「宝可梦」就停，用截图核对）。

用法：python scripts/research/firered/232_party_last_step.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party232"

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
local function do_shot(name, dump)
    shotn = shotn + 1
    local i = string.format("%02d", shotn)
    local dc = rd16(0x04000000)
    emu:screenshot(OUTP .. "/s" .. i .. "_" .. name .. ".png")
    if dump then
        for _, sp in ipairs({
            { "vram", 0x06000000, 0x18000 },
            { "ewram", 0x02000000, 0x40000 },
            { "iwram", 0x03000000, 0x8000 },
            { "pal", 0x05000000, 0x400 },
        }) do
            local d = rd(sp[2], sp[3])
            if d then wr("s" .. i .. "_" .. name .. "_" .. sp[1] .. ".bin", d) end
        end
    end
    RL(string.format("[SHOT] %02d %-16s dc=0x%04X f=%d", shotn, name, dc, RUN.f))
end

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local bn, dn = 0, 0

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
        if dc_is(0x7F60, 20) then
            phase = "press_b"; bn = 0; return
        end
        if f > 16000 then DS_DONE(1, "no-recap") end
        return
    end
    if phase == "press_b" then
        bn = bn + 1
        if bn > 10 then
            do_shot("after_recap", true)
            phase = "open"; hold = 16; setk(K.START); wait = 90
            return
        end
        setk(K.B); hold = 10; wait = 40
        return
    end

    if phase == "open" then
        do_shot("menu_top")          -- 光标应在顶部「图鉴」
        phase = "down"
        dn = 0
        return
    end

    -- DOWN 只按一次，但用 16 帧长按（231 证明 4 帧不生效）
    if phase == "down" then
        dn = dn + 1
        if dn > 1 then
            phase = "confirm"
            wait = 40
            return
        end
        hold = 16; setk(K.DOWN)
        wait = 40
        phase = "down_shot"
        return
    end
    if phase == "down_shot" then
        do_shot("down" .. dn)
        phase = "down"
        return
    end

    if phase == "confirm" then
        do_shot("on_pokemon")
        phase = "enter"
        hold = 16; setk(K.A)
        wait = 220
        return
    end

    if phase == "enter" then
        do_shot("party", true)
        RL("[PARTY] f=" .. f)
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
    r = run_lua(LUA, OUT, expect_files=["s01_after_recap.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-3000:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        print(f"  {s.name:<26} {h} {s.stat().st_size:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
