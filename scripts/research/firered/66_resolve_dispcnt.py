#!/usr/bin/env python3
"""调研(66) 解开死结：DISPCNT 说 BG 全关，但屏幕确实有菜单。

═══════════════════════════════════════════════════════════════════════════
【矛盾固定下来】
═══════════════════════════════════════════════════════════════════════════
  · probe.png 确实显示中文菜单（继续游戏/主角 RED/...）—— 已肉眼确认
  · DISPCNT = 0x3140，bit0-4 全 0（BG0-3 + OBJ 全关）—— 已用 VCOUNT/KEYINPUT
    验证 IO 读取可信（KEYINPUT 按住 A 时 bit0 正确清零）

这两个事实必须同时成立。唯一可能：

  **probe.png 与 DISPCNT 不是同一帧。**

emu_run 的 Lua 里，我在稳定 60 帧后先读 IO、再截图。
但 `emu:screenshot()` 是**异步**的，它可能等到下一帧才真正落盘。
而 DISPCNT 在菜单淡入淡出时会变（历史上看到过 0x9F40 → 0x3140）。

═══════════════════════════════════════════════════════════════════════════
【验证】
═══════════════════════════════════════════════════════════════════════════
 ① 在同一帧里**先截图、后读 IO**，看是否还矛盾
 ② 连续多帧记录 (DISPCNT, 截图的 md5)，找出「BG 开着」的那些帧
 ③ 特别关注 0x9F40（mode=4，bit8-12=0x1F）—— mode 4 是 GBA 的特殊模式

⚠ GBA BG mode：
    0 = 4bpp 常规
    1 = 2bpp+4bpp 混合
    2 = 上半屏用一套、下半屏用另一套
    3 = 8bpp
    4 = **8bpp + 全 BG 用同一套**（特殊）
    5 = 小屏

  0x3140 = mode 1，0x9F40 = mode 4。
  menu 出现时是 0x9F40（mode 4），稳定后变 0x3140（mode 1）。

  但 mode 1 也需要至少 BG0 开着才有画面…

  ⇒ **除非**：0x3140 其实不是最终状态，而是「切到别的画面」的瞬间。
     我的 stable_frames==60 判定可能撞在了两次画面切换之间。

用法：python scripts/research/firered/66_resolve_dispcnt.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "resolve"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A = 1
local proved, hold, phase = false, 0, "boot"
local last_dc, stable = -1, 0
local pressed = {}
local log_i = 0

local function setk(m) emu:setKeys(m) end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f

    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end

    if (not proved) and frame > 200 and frame % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] f=" .. frame)
        end
    end

    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1 else
            last_dc = dc; stable = 1
        end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true
            hold = 12; setk(A)
        end
        if frame > 4000 then DS_DONE(1, "no-save") end
        return
    end

    -- 读档成功：连续 24 帧，每帧记录 DISPCNT + 截图（同一帧内先截图后读）
    if frame > 400 and log_i < 24 then
        log_i = log_i + 1
        -- ★ 先截图（让 mGBA 把当前帧写出去），再读 IO
        pcall(function() emu:screenshot(OUT .. "/f" .. log_i .. ".png") end)
        local dc = emu:read16(0x04000000)
        local b0 = emu:read16(0x04000008)
        local b1 = emu:read16(0x0400000A)
        local b2 = emu:read16(0x0400000C)
        local b3 = emu:read16(0x0400000E)
        RL(string.format("[F%02d] f=%d dc=%04X BG=%04X,%04X,%04X,%04X mode=%d",
                         log_i, frame, dc, b0, b1, b2, b3, (dc>>13)&7))
    end

    if log_i >= 24 then DS_DONE(0, "logged") end
    if frame > 1200 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=400,
                rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- 逐帧 DISPCNT ---")
    for line in r.log_text.splitlines():
        print(line)

    print("\n" + "=" * 78)
    print("统计：哪些 DISPCNT 值出现")
    print("=" * 78)
    from collections import Counter
    c = Counter()
    for line in r.log_text.splitlines():
        if line.startswith("[F"):
            for tok in line.split():
                if tok.startswith("dc="):
                    c[tok[3:]] += 1
    for k, v in c.most_common():
        d = int(k, 16)
        print(f"  {k} × {v}  BG0-3={(d>>0)&0xF:04b} OBJ={(d>>4)&1} "
              f"mode={(d>>13)&7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
