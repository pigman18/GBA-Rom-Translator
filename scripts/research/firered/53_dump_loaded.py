#!/usr/bin/env python3
"""调研(53) 让 mGBA 真正读档后再 dump EWRAM（上一版停在冷启动，dump 全废）。

═══════════════════════════════════════════════════════════════════════════
【(51) 错在哪】
═══════════════════════════════════════════════════════════════════════════
(51) 只读内存、不按键，结果 2200 帧里游戏一直停在：
    d3 = 尼多王/尼多后 开场动画
    d5 = 「精灵宝可梦 赤 火红」标题画面
⇒ **存档根本没被加载**，那 6 个 dump 里的 F7 表内容不可信。

═══════════════════════════════════════════════════════════════════════════
【必须做的事】
═══════════════════════════════════════════════════════════════════════════
① 按键走完：标题 → A → 「继续游戏」 → A → 读档 → 进入世界
② **证明读档成功**：在 EWRAM 里搜存档身份字节（.sav 前 8 字节 = 玩家名）
   命中才说明这份存档真的被游戏加载了
   —— 这是 bot/run.py 的 prove() 同一套判据，别绕过它
③ 读到世界/菜单后再 dump 0x0203F2C0

用法：python scripts/research/firered/53_dump_loaded.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
OUT = ROOT / "work" / "_probe" / "ewram2"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

# 存档身份 = .sav 前 8 字节（玩家名 + 0xFF 填充），与 run.py 的 prove() 同判据
IDENT = SAVE.read_bytes()[:8].hex(" ")
print(f"存档身份字节（前 8 B）：{IDENT}")


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


LUA = r'''
local OUT = os.getenv("EMU_OUT")
local IDENT_HEX = os.getenv("EMU_IDENT")     -- "xx xx xx ..." 8 字节

local lg = assert(io.open(OUT .. "/dump.log", "w"), "cannot open log")
local function log(s) lg:write(s .. "\n"); lg:flush() end

local function wr(path, data)
    local f = assert(io.open(path, "wb"), "cannot write " .. path)
    f:write(data); f:close()
end

-- 把 "xx xx .." 转成 Lua 字符串
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(IDENT_HEX)

local frame = 0
local phase = "boot"
local hold = 0
local mask = 0
local dumped = 0
local proved = false
local prove_frame = 0

local A, B, START, DOWN = 1, 2, 8, 128

local function setk(m) mask = m; emu:setKeys(m) end

callbacks:add("frame", function()
    frame = frame + 1

    -- 每帧检查存档身份是否已进 EWRAM（1MB 全搜，用 find）
    if not proved and frame % 30 == 0 and frame > 300 then
        local ok, ew = pcall(function() return emu:readRange(0x02000000, 0x40000) end)
        if ok and ew and ew:find(IDENT, 1, true) then
            proved = true
            prove_frame = frame
            log("[PROVE] 存档已加载 f=" .. frame)
        end
    end

    -- 按键时序：进标题后按 A 进主菜单，再按 A 选「继续游戏」
    if frame == 400 then setk(A) hold = 12; phase = "t1" end
    if phase == "t1" and hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0); phase = "w1" end
    end
    if phase == "w1" and frame > 520 then setk(A) hold = 12; phase = "t2" end
    if phase == "t2" and hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0); phase = "w2" end
    end
    if phase == "w2" and frame > 700 then setk(A) hold = 12; phase = "t3" end
    if phase == "t3" and hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0); phase = "wait" end
    end

    -- 读档成功后，等画面稳定再 dump
    if proved and frame > prove_frame + 240 and frame % 240 == 0 and dumped < 8 then
        dumped = dumped + 1
        local tag = OUT .. "/d" .. dumped
        wr(tag .. ".ewram.bin", emu:readRange(0x02000000, 0x40000))
        wr(tag .. ".iwram.bin", emu:readRange(0x03000000, 0x8000))
        wr(tag .. ".vram.bin",  emu:readRange(0x06000000, 0x18000))
        wr(tag .. ".pal.bin",   emu:readRange(0x05000000, 0x400))
        wr(tag .. ".io.bin",    emu:readRange(0x04000000, 0x60))
        wr(tag .. ".f7table.bin", emu:readRange(0x0203F2C0, 0x400))
        emu:screenshot(tag .. ".png")
        log(string.format("[D%d] f=%d dispcnt=%04X", dumped, frame,
                          emu:read16(0x04000000)))
    end

    if frame > 3200 then
        log("done f=" .. frame .. " proved=" .. tostring(proved))
        lg:close()
        emu:exit()
    end
end)
'''


def main() -> int:
    mgba = find_mgba()
    if OUT.exists():
        for f in OUT.glob("*"):
            f.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    lua_path = OUT / "_dump.lua"
    lua_path.write_text(LUA, encoding="utf-8")

    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_IDENT"] = IDENT

    print(f"mGBA : {mgba.name}")
    print(f"OUT  : {OUT}")
    print("启动（约 3200 帧，含读档按键）…")
    p = subprocess.Popen([str(mgba), "--script", str(lua_path), str(rom_copy)],
                         env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=900)
        if out:
            txt = out.decode("utf-8", "replace")
            if txt.strip():
                print("--- mGBA stdout ---")
                print(txt[:3000])
    except subprocess.TimeoutExpired:
        p.kill()
        print("超时强杀")

    lg = OUT / "dump.log"
    if lg.exists():
        print("--- dump.log ---")
        print(lg.read_text(encoding="utf-8", errors="replace"))
    else:
        print("**没有 dump.log —— 脚本没跑起来或崩了**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
