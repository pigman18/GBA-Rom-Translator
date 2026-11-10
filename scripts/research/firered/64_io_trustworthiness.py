#!/usr/bin/env python3
"""调研(64) 关键验证：mGBA 的 emu:read16 对 IO 区（0x04xxxxxx）是否可信。

═══════════════════════════════════════════════════════════════════════════
【矛盾】
═══════════════════════════════════════════════════════════════════════════
(62) 证明 emu:readRange 对 **ROM 区**可信（与 ROM 文件逐字节一致）。
但读 **IO 区** 得到的所有 DISPCNT 都是「BG0-3 全关」：
    0x0140 / 0x1040 / 0x5840 / 0x1E40 / 0x9F40 / 0x3140
这些值的 bit0-3 **全是 0**。而屏幕明明有画面。

GBA 不可能在 BG 全关时显示文字。⇒ 读数不可信。

═══════════════════════════════════════════════════════════════════════════
【验证设计（只用一个已知真值）】
═══════════════════════════════════════════════════════════════════════════
GBA 的 IO 区没有「文件真值」可对照。所以换思路：

**用 VCOUNT 做体检。** VCOUNT(0x04000006) 只可能 0..227，且每帧扫过 0..227。
若读到的 VCOUNT 恒为 0x9629 或跳变成不可能的值 ⇒ 这个路径读 IO 有问题。

**再用一个更强的自证：读 0x04000006 多次，看它是否随扫描线推进。**
  · 若每帧在 0..227 之间变化 ⇒ IO 读法正常，那 DISPCNT 就是这个值
  · 若恒为怪值 ⇒ IO 读法有问题

**第三个证据：读 KEYINPUT(0x04000130)。**
  它反映当前按键状态，我可以在 Lua 里按住 A 再读，能对上就是真值。

用法：python scripts/research/firered/64_io_trustworthiness.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "iotrust"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local proved = false
local A = 1
local phase = "idle"

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f

    if (not proved) and frame % 60 == 0 and frame > 240 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] f=" .. frame)
        end
    end

    -- 探针：在若干帧上密集读 VCOUNT / DISPCNT / KEYINPUT
    if proved and frame > 900 and phase == "idle" then
        phase = "probe"

        -- ① VCOUNT 连续读 20 次（同一帧内，理论上应该几乎不变）
        local vc = {}
        for i = 1, 20 do
            local ok, v = pcall(function() return emu:read16(0x04000006) end)
            vc[#vc+1] = ok and string.format("%04X", v) or "ERR"
        end
        RL("[VCOUNT x20] " .. table.concat(vc, " "))

        -- ② 跨帧采样 VCOUNT：每 3 帧读一次，看是否在 0..227
        RL("[VCOUNT@frame] " .. string.format("%d:%04X", frame,
             emu:read16(0x04000006)))

        -- ③ KEYINPUT：先读「没按键」的值
        local okk1, k1 = pcall(function() return emu:read16(0x04000130) end)
        RL("[KEYINPUT idle] " .. (okk1 and string.format("%04X", k1) or "ERR"))

        -- ④ 按住 A 再读（A = bit0 = 0 表示按下）
        emu:setKeys(A)
        local okk2, k2 = pcall(function() return emu:read16(0x04000130) end)
        RL("[KEYINPUT A-down] " .. (okk2 and string.format("%04X", k2) or "ERR"))
        emu:setKeys(0)

        -- ⑤ 同时刻的 DISPCNT / BGxCNT（只信 +0x00..+0x0F）
        local ds = emu:read16(0x04000000)
        local b0 = emu:read16(0x04000008)
        local b1 = emu:read16(0x0400000A)
        local b2 = emu:read16(0x0400000C)
        local b3 = emu:read16(0x0400000E)
        RL(string.format("[REGS] DISPCNT=%04X BG0=%04X BG1=%04X BG2=%04X BG3=%04X",
                         ds, b0, b1, b2, b3))

        -- ⑥ 用 emu:readRange 读同样 16 字节，交叉验证
        local rng = emu:readRange(0x04000000, 0x10)
        local h = {}
        for i = 1, #rng do h[#h+1] = string.format("%02X", rng:byte(i)) end
        RL("[RANGE16] " .. table.concat(h, " "))

        DS_DONE(0, "probed")
    end

    if proved and frame > 1100 then DS_DONE(1, "late") end
    if frame > 3000 then DS_DONE(1, "timeout") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=900,
                rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- 探针 ---")
    for line in r.log_text.splitlines():
        print(line)
    print("\n" + "=" * 78)
    print("判读")
    print("=" * 78)
    print("  · VCOUNT 若恒为同一个怪值（如 0x9629）⇒ IO 读法有问题")
    print("  · VCOUNT 若在 0..227 之间（0x0000-0x00E3）⇒ IO 读法正常")
    print("  · KEYINPUT 若 A-down 比 idle 小（bit0 清零）⇒ IO 读法正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
