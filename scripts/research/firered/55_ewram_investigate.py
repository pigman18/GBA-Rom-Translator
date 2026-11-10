#!/usr/bin/env python3
"""调研(55) 用 emu_run 重采 EWRAM，并正面回答「有没有解压算法」。

═══════════════════════════════════════════════════════════════════════════
【(53) 的结论为什么不可信】
═══════════════════════════════════════════════════════════════════════════
(53) 用的是裸 subprocess，Lua 里的 `emu:exit()` 是 nil（实测 API 不存在），
实际一直在抛错。加上 (51) 停在冷启动，数据全废。

这次全部走 emu_run：
  · 每个 callback 用 WRAP 包裹，出错必记 [LUA-ERR]
  · 收尾写 [DONE]，跑完由 Python 侧校验帧数/产出/错误
  · 校验不过直接 FAIL，不产出「看起来成功」的结果

═══════════════════════════════════════════════════════════════════════════
【要查什么】
═══════════════════════════════════════════════════════════════════════════
静态分析说：转码函数 @0x081DB660 用 `TABLE[hi]`（0x0203F2C0 + hi*4）。
但 (53) 实测该地址是 **全 0**。

两种可能：
  a) 我算错了基址/偏移
  b) 那张表根本不是这么用

⇒ 正确做法：**不预设地址**，直接在整个 EWRAM 里找「像 F7 表的东西」：
   一群连续 u32，大多指向 ROM，且指向的内容以 0xFF 结尾的单字节串。

同时把「是否解压」一起判：若表项指向的数据高熵/无 0xFF 结尾 ⇒ 是压缩数据。

用法：python scripts/research/firered/55_ewram_investigate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "ewram3"

# 存档身份 = .sav 前 8 字节，用于 prove 读档成功
IDENT = SAVE_FR.read_bytes()[:8]
IDENT_HEX = IDENT.hex()

LUA = r'''
local NTAG = 6
local dumped = 0
local hold, phase = 0, "boot"
local A, B, START = 1, 2, 8

-- 存档身份（8 字节），由 Python 通过环境变量传入的十六进制串还原
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local proved = false

local function setk(m) emu:setKeys(m) end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local frame = RUN.f

    -- 每 60 帧检查存档是否已加载进 EWRAM
    if (not proved) and frame % 60 == 0 and frame > 240 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            RL("[PROVE] save loaded at f=" .. frame)
        end
    end

    -- 按键：标题 → A；主菜单 → A 选继续游戏；再 A 确认
    if frame == 360 then setk(A); hold = 10; phase = "t1" end
    if phase == "t1" then
        hold = hold - 1
        if hold <= 0 then setk(0); phase = "w1" end
    elseif phase == "w1" and frame > 460 then
        setk(A); hold = 10; phase = "t2"
    elseif phase == "t2" then
        hold = hold - 1
        if hold <= 0 then setk(0); phase = "w2" end
    elseif phase == "w2" and frame > 640 then
        setk(A); hold = 10; phase = "t3"
    elseif phase == "t3" then
        hold = hold - 1
        if hold <= 0 then setk(0); phase = "wait" end
    end

    -- 读档成功后再开始批量 dump（每 200 帧一个，覆盖不同界面）
    if proved and frame > 760 and frame % 200 == 0 and dumped < NTAG then
        dumped = dumped + 1
        local tag = OUT .. "/s" .. dumped
        -- 逐个 dump，每个都单独 pcall，一个失败不影响其他的。
        -- ⚠ 变量名不要用 io —— 会遮蔽 Lua 的 io 库，导致 io.open 变 nil
        --   （2026-11-04 踩过：只在帧回调里出错，脚本前面一切正常）
        local SEGS = {
            { suf = ".ewram.bin", addr = 0x02000000, len = 0x40000 },
            { suf = ".vram.bin",  addr = 0x06000000, len = 0x18000 },
            { suf = ".pal.bin",   addr = 0x05000000, len = 0x400 },
            { suf = ".ioblk.bin", addr = 0x04000000, len = 0x60 },
            { suf = ".iwram.bin", addr = 0x03000000, len = 0x8000 },
        }
        local wrote = 0
        for _, S in ipairs(SEGS) do
            local okr, blob = pcall(function() return emu:readRange(S.addr, S.len) end)
            if okr and blob then
                local okw = pcall(function()
                    local fp = assert(io.open(tag .. S.suf, "wb"))
                    fp:write(blob); fp:close()
                end)
                if okw then wrote = wrote + 1 end
            end
        end
        pcall(function() emu:screenshot(tag .. ".png") end)
        RL(string.format("[D%d] f=%d dispcnt=%04X segs=%d", dumped, frame,
                         emu:read16(0x04000000), wrote))
    end

    if proved and frame > 2000 then
        DS_DONE(0, "collected")
    end
    if frame > 5000 then
        DS_DONE(1, "timeout-no-prove")
    end
end))
'''

EXPECT = []
for i in range(1, 7):
    EXPECT += [f"s{i}.ewram.bin", f"s{i}.vram.bin", f"s{i}.png"]

def main() -> int:
    print(f"存档身份：{IDENT_HEX}")
    r = run_lua(LUA, OUT, expect_files=EXPECT, min_frames=1500,
                rom=ROM_ZH, save=SAVE_FR, timeout=600,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    if not r.ok:
        print("\n采集失败，不进入分析（避免拿脏数据下结论）")
        return 1
    print("\n采集成功。产出：")
    for f in sorted(OUT.glob("s*.bin")):
        print(f"  {f.name}  {f.stat().st_size:,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
