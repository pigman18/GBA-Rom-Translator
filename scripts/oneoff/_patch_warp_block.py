#!/usr/bin/env python3
"""把 bot.lua 里的 warp 实现块替换成简化版（按行号精确替换）。

为什么要这个脚本：之前两次用字符串替换都误删了别处的 `else` 分支，
导致「语法合法但语义被吞」的静默卡死。改成按行号定位、显式校验边界，
替换完立刻调 lint 验证。

用法：python scripts/_patch_warp_block.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent.parent / "bot" / "bot.lua"

NEW_BLOCK = '''-- 按键序列（实测成功的那条），运行时按 mon 展开成扁平列表：
--   START → UP×8 → DOWN×1 → A →（DOWN × mon）→ A → A
local function warp_build_seq(mon)
    local seq = {}
    local function tap(k, n, after)
        seq[#seq + 1] = { key = k, hold = n, wait = after or 0 }
    end
    tap("START", 4, 60)
    for _ = 1, 8 do tap("UP", 4, 6) end
    tap("DOWN", 4, 12)
    tap("A", 4, 80)
    for _ = 1, mon do tap("DOWN", 4, 22) end
    tap("A", 4, 70)
    tap("A", 4, 40)
    return seq
end

local WARP_SEQ = nil
local WARP_SEQI = 0
local WARP_HOLD = 0
local WARP_WAIT = 0

-- 返回 true = 本帧被 warp 占用
local function warp_step(fr)
    if not WARP_ACTIVE then return false end

    local x, y, mg, mn = warp_pos()
    if x ~= nil and (mg ~= WARP_MAPG0 or mn ~= WARP_MAPN0) then
        emu:setKeys(0)
        WARP_ACTIVE = false
        log(string.format(
            "[WARP] hit f=%d map=%d:%d grid=(%d,%d) target=%d:%d (%d,%d)%s",
            fr, mg, mn, x, y, WARP_TMAPG, WARP_TMAPN, WARP_TX, WARP_TY,
            (mg == WARP_TMAPG and mn == WARP_TMAPN
             and x == WARP_TX and y == WARP_TY) and " OK 完全命中" or " (部分偏差)"))
        advance(fr)
        return true
    end

    if WARP_PHASE == "set" then
        local sb1 = SB2_RUNTIME + SB1_DELTA
        emu:write8(sb1 + 0x1C, WARP_TMAPG & 0xFF)
        emu:write8(sb1 + 0x1D, WARP_TMAPN & 0xFF)
        emu:write8(sb1 + 0x1E, 0xFF)
        emu:write8(sb1 + 0x1F, 0x00)
        emu:write16(sb1 + 0x20, WARP_TX & 0xFFFF)
        emu:write16(sb1 + 0x22, WARP_TY & 0xFFFF)
        log(string.format(
            "[WARP] set lastHealLocation f=%d -> %d:%d (%d,%d)",
            fr, WARP_TMAPG, WARP_TMAPN, WARP_TX, WARP_TY))
        WARP_PHASE = "keys"
        WARP_SEQI = 1
        WARP_HOLD, WARP_WAIT = 0, 0
        WARP_T0 = fr
        return true
    end

    if WARP_SEQI > #WARP_SEQ then
        if fr - WARP_T0 > WARP_TO then
            emu:setKeys(0)
            WARP_ACTIVE = false
            log(string.format(
                "[WARP] TIMEOUT f=%d 按完序列仍未换图（map 仍 %d:%d）"
                .. " -> 检查存档里是否真有传送术", fr, mg or -99, mn or -99))
            advance(fr)
            return true
        end
        return true
    end

    local st2 = WARP_SEQ[WARP_SEQI]

    if WARP_WAIT > 0 then
        WARP_WAIT = WARP_WAIT - 1
        return true
    end

    if WARP_HOLD > 0 then
        emu:setKeys(1 << KEYBIT[st2.key])
        WARP_HOLD = WARP_HOLD - 1
        if WARP_HOLD == 0 then
            emu:setKeys(0)
            WARP_WAIT = st2.wait
        end
        return true
    end

    WARP_HOLD = st2.hold
    return true
end
'''


def main() -> int:
    lines = BOT.read_text(encoding="utf-8").splitlines(keepends=True)

    # 边界：从「按键序列（实测成功的那条）：」注释行开始，
    # 到「-- ── 多帧连续采集」之前结束
    start = None
    end = None
    for i, ln in enumerate(lines):
        if start is None and ln.startswith("-- 按键序列（实测成功的那条）："):
            start = i
        elif start is not None and ln.startswith("-- ── 多帧连续采集"):
            end = i
            break

    if start is None or end is None:
        print(f"[ERR] 找不到边界 start={start} end={end}")
        return 1
    print(f"替换行 {start + 1}..{end}（共 {end - start} 行）")
    print(f"  首行: {lines[start].rstrip()[:60]}")
    print(f"  末行(前一行): {lines[end - 1].rstrip()[:60]}")

    out = lines[:start] + [NEW_BLOCK] + lines[end:]
    BOT.write_text("".join(out), encoding="utf-8")
    print("[OK] 已写回 bot/bot.lua")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
