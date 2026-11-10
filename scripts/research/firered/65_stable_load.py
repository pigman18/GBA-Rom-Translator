#!/usr/bin/env python3
"""调研(65) 稳定的读档 + IO 真实性验证（解决 (64) 的读档失败）。

═══════════════════════════════════════════════════════════════════════════
【(64) 的失败】
═══════════════════════════════════════════════════════════════════════════
脚本跑到 f=3001 都没等到 [PROVE]（存档未加载）。
而 (61) 在 f=780 就成功了。两次的按键时序**完全一样**。

⇒ 读档成功与否取决于**游戏当时处在哪个画面**。
   固定 frame 号按 A 是脆弱的：开场动画长度可能有随机差异。

═══════════════════════════════════════════════════════════════════════════
【正确做法：状态驱动，不用帧号】
═══════════════════════════════════════════════════════════════════════════
沿用 bot/_lib.lua 的教训（"等状态，不等帧数"）：

① 轮询 DISPCNT，识别当前处于哪个阶段
② 在「标题画面」出现后按 A
③ 在「继续游戏菜单」出现后按 A
④ 用 [PROVE] 确认读档成功；失败则**重试**（回到标题再按一次）
⑤ 一旦 proved，再读 IO 做验证

同时把每一步的状态都记进日志，失败时能看到卡在哪一步。

═══════════════════════════════════════════════════════════════════════════
【要验证的（这是本轮的核心）】
═══════════════════════════════════════════════════════════════════════════
  V1 VCOUNT 是否在 0..227 之间（GBA 硬约束）
  V2 KEYINPUT 按住 A 时 bit0 是否清零
  V3 DISPCNT 的 BG0-3 是否至少有一个开

若 V1 或 V2 不成立 ⇒ mGBA 的 IO 读法不可信，之前所有 tilemap 分析作废。
若 V1/V2 成立而 V3 不成立 ⇒ 说明菜单确实不用 BG（可能走 OBJ/特殊模式）。

用法：python scripts/research/firered/65_stable_load.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "stableload"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A, B, START = 1, 2, 8

local proved = false
local hold = 0
local last_dc = -1
local stable_frames = 0
local pressed_at = {}      -- 记录已按过的 DISPCNT，避免同一画面反复按
local phase_log = {}
local probe_done = false

local function setk(m) emu:setKeys(m) end

-- 状态驱动按键：某个 DISPCNT 稳定 N 帧且没按过，就按一次 A
local function try_press(dc, n)
    if dc == last_dc then
        stable_frames = stable_frames + 1
    else
        last_dc = dc
        stable_frames = 1
    end
    if stable_frames == n and not pressed_at[dc] then
        pressed_at[dc] = true
        hold = 12
        setk(A)
        phase_log[#phase_log+1] = string.format("press@%d dc=%04X", RUN.f, dc)
    end
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f

    -- 按键保持
    if hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0) end
        return
    end

    -- 存档加载检测
    if (not proved) and frame > 200 and frame % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL(string.format("[PROVE] f=%d", frame))
        end
    end

    if proved then
        -- 读档成功后：先等画面稳定，再做探针
        if (not probe_done) and frame > 100 then
            local dc = emu:read16(0x04000000)
            if dc == last_dc then
                stable_frames = stable_frames + 1
            else
                last_dc = dc
                stable_frames = 1
            end
            if stable_frames == 60 then
                probe_done = true

                -- V1: VCOUNT 采样 20 次
                local vc = {}
                local bad = 0
                for i = 1, 20 do
                    local ok, v = pcall(function() return emu:read16(0x04000006) end)
                    if ok then
                        vc[#vc+1] = string.format("%03X", v)
                        if v > 227 then bad = bad + 1 end
                    end
                end
                RL("[V1 VCOUNT] " .. table.concat(vc, " ")
                   .. "  超出227的:" .. bad)

                -- V2: KEYINPUT
                local k0 = emu:read16(0x04000130)
                emu:setKeys(A)
                local k1 = emu:read16(0x04000130)
                emu:setKeys(0)
                RL(string.format("[V2 KEYINPUT] idle=%04X A-down=%04X (bit0=%d)",
                                 k0, k1, k1 & 1))

                -- V3: DISPCNT
                local dc2 = emu:read16(0x04000000)
                RL(string.format("[V3 DISPCNT] %04X  BG0-3=%d%d%d%d OBJ=%d mode=%d",
                                 dc2, (dc2>>0)&1, (dc2>>1)&1, (dc2>>2)&1,
                                 (dc2>>3)&1, (dc2>>4)&1, (dc2>>13)&7))

                -- V4: 完整 16 字节
                local rng = emu:readRange(0x04000000, 0x10)
                local h = {}
                for i = 1, #rng do h[#h+1] = string.format("%02X", rng:byte(i)) end
                RL("[V4 RANGE16] " .. table.concat(h, " "))

                -- 顺便存一帧图和内存
                pcall(function()
                    local fp = assert(io.open(OUT .. "/probe.vram.bin", "wb"))
                    fp:write(emu:readRange(0x06000000, 0x18000)); fp:close()
                end)
                pcall(function()
                    local fp = assert(io.open(OUT .. "/probe.pal.bin", "wb"))
                    fp:write(emu:readRange(0x05000000, 0x400)); fp:close()
                end)
                pcall(function()
                    local fp = assert(io.open(OUT .. "/probe.io.bin", "wb"))
                    fp:write(emu:readRange(0x04000000, 0x10)); fp:close()
                end)
                pcall(function() emu:screenshot(OUT .. "/probe.png") end)

                RL("[PHASES] " .. table.concat(phase_log, " | "))
                DS_DONE(0, "probed")
            end
        end
        return
    end

    -- 未读档：状态驱动地按 A
    local dc = emu:read16(0x04000000)
    try_press(dc, 40)

    if frame > 4000 then
        RL("[FAIL] 读档失败，DISPCNT 历史=" .. table.concat(phase_log, " | "))
        DS_DONE(1, "no-save-loaded")
    end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT,
                expect_files=["probe.vram.bin", "probe.png"],
                min_frames=1000, rom=ROM_ZH, save=SAVE_FR, timeout=400,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print("\n--- 探针 ---")
    for line in r.log_text.splitlines():
        print(line)
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
