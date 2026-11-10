#!/usr/bin/env python3
"""调研(75) 定案：mGBA 的 readRange 对哪些地址段返回的是「快照/缓存」。

═══════════════════════════════════════════════════════════════════════════
【累积的证据】
═══════════════════════════════════════════════════════════════════════════
  E1 emu:readRange(0x08000000) 与 ROM 文件逐字节一致 ⇒ 可信
  E2 emu:readRange(0x04000000) ≈ IWRAM 开头 16 字节的 14/16 ⇒ **不是真 IO**
  E3 6 次 dump 的 VRAM MD5 **完全相同**（52fc9d7c5310），但同批 6 张 PNG 不同
     ⇒ **VRAM 是冻结快照，没随画面更新**
  E4 VRAM 里只有 72 个「有形状」tile（全是菜单边框），**没有任何文字字形**
  E5 对 VRAM 穷举所有 charBase/screenBase/bpp，最佳还原度 0.7%

⇒ 结论：**VRAM 读数不可信**（至少在菜单画面期间是冻结的）。

═══════════════════════════════════════════════════════════════════════════
【决定性测试：同一帧内连续读 VRAM 两次，中间跨越画面变化】
═══════════════════════════════════════════════════════════════════════════
若 VRAM 读数真的冻结，那么：
  · 按 A 键让菜单变化（例如进入「继续游戏」→ 世界画面）
  · 变化前后的 VRAM 读数应该**完全相同**
  · 但截图应该不同

这能一次性定性：是 readRange 的锅，还是我看错了。

同时测：用 read8 逐字节读 VRAM 一小段，看是否与 readRange 一致。
若 read8 与 readRange 不同 ⇒ 说明 readRange 有缓存层。

用法：python scripts/research/firered/75_vram_frozen.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "frozen"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A = 1
local proved, hold, last_dc, stable = false, 0, -1, 0
local pressed = {}
local step = 0

local function setk(m) emu:setKeys(m) end
local function md5ish(b)
    -- 简易指纹（不引外部库）：取长度 + 若干采样字节异或
    local s = 0
    for i = 1, #b, 97 do s = (s * 31 + b:byte(i)) % 4294967296 end
    return string.format("%08X_%d", s, #b)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end

    if (not proved) and frame > 200 and frame % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true; RL("[PROVE] f=" .. frame)
        end
    end

    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1 else
            last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true; hold = 12; setk(A) end
        if frame > 4000 then DS_DONE(1, "no-save") end
        return
    end

    -- T1：读档后立刻记录 VRAM 指纹
    if frame == 700 and step == 0 then
        step = 1
        local v = emu:readRange(0x06000000, 0x18000)
        RL("[T1 VRAM] " .. md5ish(v) .. "  f=" .. frame)
        -- 同时用 read8 读前 64 字节，与 readRange 前 64 对比
        local b8 = {}
        for o = 0, 63 do
            local ok, x = pcall(function() return emu:read8(0x06000000 + o) end)
            b8[#b8+1] = ok and string.format("%02X", x) or "??"
        end
        RL("[T1 read8] " .. table.concat(b8, " "))
        local r64 = emu:readRange(0x06000000, 64)
        local rh = {}
        for i = 1, #r64 do rh[#rh+1] = string.format("%02X", r64:byte(i)) end
        RL("[T1 range64] " .. table.concat(rh, " "))
        RL(string.format("[T1 IO] dc=%04X", emu:read16(0x04000000)))
        pcall(function() emu:screenshot(OUT .. "/t1.png") end)
    end

    -- T2：按 A 进游戏世界（画面必然大变），再记录
    if frame == 800 and step == 1 then
        step = 2
        setk(A); hold = 12
    elseif frame == 1100 and step == 2 then
        step = 3
        local v = emu:readRange(0x06000000, 0x18000)
        RL("[T2 VRAM] " .. md5ish(v) .. "  f=" .. frame)
        local r64 = emu:readRange(0x06000000, 64)
        local rh = {}
        for i = 1, #r64 do rh[#rh+1] = string.format("%02X", r64:byte(i)) end
        RL("[T2 range64] " .. table.concat(rh, " "))
        RL(string.format("[T2 IO] dc=%04X", emu:read16(0x04000000)))
        pcall(function() emu:screenshot(OUT .. "/t2.png") end)
        DS_DONE(0, "done")
    end
    if frame > 2000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=["t1.png", "t2.png"],
                min_frames=700, rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- 探针 ---")
    for line in r.log_text.splitlines():
        print(line[:400])
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
