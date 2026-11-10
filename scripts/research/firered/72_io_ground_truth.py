#!/usr/bin/env python3
"""调研(72) 铁证：把读取结果与「GBA 不可能的值」对照，定性 IO 读取是否可信。

═══════════════════════════════════════════════════════════════════════════
【已排除】
═══════════════════════════════════════════════════════════════════════════
  · emu:readRange 对 **ROM 区**可信（(62) 与 ROM 文件逐字节一致）
  · emu:read16 KEYINPUT@0x04000130 可信（按 A 时 bit0 正确清零）
  · emu:read16 VCOUNT@0x04000006 = 0x00A0（合法值，160）

【互相矛盾的读数】
   0x04000004 = 0x9629   ← VCOUNT 不可能 > 227，但 0x04000004 就是 VCOUNT
   0x04000006 = 0x00A0   ← 合法 VCOUNT 值出现在 BG0CNT 的位置
   0x04000008 = 0x1E00
   0x04000010 = 0x1C18  ← BG0HOFS 不可能是 0x1C18（横向偏移最大 511）
   0x04000012 = 0x1C18  ← BG0VOFS 同上，且与 HOFS 相同（不可能）

⇒ **`0x04000004` 起到后面全是错位的**。

【关键假设：mGBA 的 read16 对 IO 的「读地址」有 2 字节偏移】
   若 `read16(0x04000004)` 实际读的是 `0x04000006`，则：
     read16(0x04000004)=0x9629 → 其实 0x04000006 的内容是 0x9629？
     但 read16(0x04000006)=0x00A0，自相矛盾。

【真正可行的判据：找「VCOUNT 一定在 0..227」的位置】
   扫 0x04000000..0x04000060，把值 <= 227 的位置列出来，
   再结合 GBA 手册对照，就能定出每个读数的真实归属。

【同时用第二条铁证：IWRAM 首地址】
   0x03000000 是 IWRAM 起始，通常存 BIOS 跳板或空闲。
   (62) 实测 [IWRAM2] = 40 5C 00 00 2B 96 00 00 ...
   而 [IO] 也是 40 5C 00 00 29 96 ...
   **两个不同区域的前 8 字节几乎相同** ⇒ 强烈暗示 mGBA 的 readRange
   在某些地址上返回了**同一块缓存**。

用法：python scripts/research/firered/72_io_ground_truth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "groundtruth"
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
local phase = 0

local function setk(m) emu:setKeys(m) end

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

    if frame == 700 and phase == 0 then
        phase = 1

        -- ① 扫 0x04000000..0x04000060 全部 u16
        local t = {}
        for o = 0, 0x60, 2 do
            local ok, v = pcall(function() return emu:read16(0x04000000 + o) end)
            t[#t+1] = string.format("%02X:%04X", o, ok and v or -1)
        end
        RL("[IO_SCAN] " .. table.concat(t, " "))

        -- ② 对比三个不同区域的「前 8 字节」，看是否相同（同一缓存的铁证）
        local function head(addr)
            local ok, b = pcall(function() return emu:readRange(addr, 8) end)
            if not ok then return "ERR" end
            local h = {}
            for i = 1, #b do h[#h+1] = string.format("%02X", b:byte(i)) end
            return table.concat(h, " ")
        end
        RL("[HEAD 0x02000000] " .. head(0x02000000))
        RL("[HEAD 0x03000000] " .. head(0x03000000))
        RL("[HEAD 0x04000000] " .. head(0x04000000))
        RL("[HEAD 0x05000000] " .. head(0x05000000))
        RL("[HEAD 0x06000000] " .. head(0x06000000))
        RL("[HEAD 0x07000000] " .. head(0x07000000))
        RL("[HEAD 0x08000000] " .. head(0x08000000))

        -- ③ 用 read8 逐字节读 0x04000000..0x0400000F，与 read16 交叉验证
        local b8 = {}
        for o = 0, 0x0F do
            local ok, v = pcall(function() return emu:read8(0x04000000 + o) end)
            b8[#b8+1] = ok and string.format("%02X", v) or "ERR"
        end
        RL("[IO_READ8] " .. table.concat(b8, " "))

        -- ④ 读 VRAM 前 16 字节（已知应全是 0 或 tile 数据）
        local vh = {}
        for o = 0, 0x0F do
            local ok, v = pcall(function() return emu:read8(0x06000000 + o) end)
            vh[#vh+1] = ok and string.format("%02X", v) or "ERR"
        end
        RL("[VRAM_READ8] " .. table.concat(vh, " "))

        DS_DONE(0, "scan")
    end
    if frame > 1200 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=600,
                rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- 扫描 ---")
    for line in r.log_text.splitlines():
        print(line)
    print("\n" + "=" * 78)
    print("判读：若多个区域的 HEAD 完全相同 ⇒ readRange 有地址混淆")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
