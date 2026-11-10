#!/usr/bin/env python3
"""调研(62) 定位 mGBA Lua 读 IO 的真实行为 —— 为什么 VCOUNT=0x9629。

═══════════════════════════════════════════════════════════════════════════
【(61) 的硬证据】
═══════════════════════════════════════════════════════════════════════════
  [RANGE]  0x04000000 起: 40 31 00 00 29 96 A0 00 00 1E 00 00 00 00 0F 1C
  [READ16] 00=3140 02=0000 04=9629 06=00A0 08=1E00 0A=0000 0C=0000 0E=1C0F
  [IWRAM]  0x03000000 起: 40 31 00 00 2B 96 00 00 00 1E 00 00 00 00 0F 1C

⇒ 两个致命矛盾：
  ① **VCOUNT = 0x9629** —— VCOUNT 只可能 0..227，不可能是这个值
  ② **IWRAM 开头与 IO 开头几乎相同**（只有第 5 字节差 2）——
     这两个区不可能一样

⇒ 唯一解释：我读到的**不是真正的内存**。
   要么 mGBA 的 emu:read* 把地址当成了「ROM 偏移」，
   要么这个 mGBA 构建的 Lua API 语义与文档不同。

═══════════════════════════════════════════════════════════════════════════
【验证：拿已知内容做对照】
═══════════════════════════════════════════════════════════════════════════
 GBA 启动后 ROM 头（0x08000000 起 0xC0）是固定的：
   +0x00..0x03 = 32 字节 ARM 跳转指令
   +0xA0..0xAB = 游戏代码（BPRJ 日版）
 若 emu:readRange(0x08000000, 0xC0) 返回的内容 == ROM 文件前 0xC0 ⇒ 读法正确
 若不等 ⇒ 读法有问题，之前所有内存分析都要作废

这不是「又换个方向猜」，是**先证明工具可信**，否则后面每一步都是空中楼阁。

用法：python scripts/research/firered/62_verify_read_semantics.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, ROM_ZH, ROM_JA   # noqa: E402

OUT = ROOT / "work" / "_probe" / "readsanity"

LUA = r'''
callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    if RUN.f < 400 then return end

    local function dump_hex(blob)
        local t = {}
        for i = 1, #blob do t[#t+1] = string.format("%02X", blob:byte(i)) end
        return table.concat(t, " ")
    end

    -- ① ROM 头：与 ROM 文件前 0xC0 对比（ROM 是只读的，最容易验证）
    local ok, romhead = pcall(function() return emu:readRange(0x08000000, 0xC0) end)
    RL("[ROMHEAD] " .. (ok and dump_hex(romhead) or "ERR"))

    -- ② 用已知的「游戏代码」区再验一次
    local ok2, rom2 = pcall(function() return emu:readRange(0x080000A0, 0x20) end)
    RL("[ROM_A0] " .. (ok2 and dump_hex(rom2) or "ERR"))

    -- ③ VRAM 开头（0x06000000）—— 应全是 0 或 tile 数据
    local ok3, v = pcall(function() return emu:readRange(0x06000000, 0x20) end)
    RL("[VRAM] " .. (ok3 and dump_hex(v) or "ERR"))

    -- ④ EWRAM 开头（0x02000000）
    local ok4, e = pcall(function() return emu:readRange(0x02000000, 0x20) end)
    RL("[EWRAM] " .. (ok4 and dump_hex(e) or "ERR"))

    -- ⑤ IWRAM（0x03000000）—— 与 IO 对比
    local ok5, i = pcall(function() return emu:readRange(0x03000000, 0x20) end)
    RL("[IWRAM2] " .. (ok5 and dump_hex(i) or "ERR"))

    -- ⑥ IO（0x04000000）
    local ok6, o = pcall(function() return emu:readRange(0x04000000, 0x20) end)
    RL("[IO] " .. (ok6 and dump_hex(o) or "ERR"))

    -- ⑦ 换个方式：用 read8 逐字节读 IO 前 8 字节
    local b = {}
    for k = 0, 7 do
        local okk, vv = pcall(function() return emu:read8(0x04000000 + k) end)
        b[#b+1] = okk and string.format("%02X", vv) or "ERR"
    end
    RL("[IO read8] " .. table.concat(b, " "))

    -- ⑧ 检查 mGBA 版本信息
    RL("[VERSION] " .. tostring(main and main.version and main.version() or "n/a"))

    DS_DONE(0, "sanity")
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=[], min_frames=400,
                rom=ROM_ZH, timeout=180)
    print(r.report())
    print("\n--- 探针结果 ---")
    for line in r.log_text.splitlines():
        print(line)

    # 与 ROM 文件比对
    print("\n" + "=" * 78)
    print("与 ROM 文件对照")
    print("=" * 78)
    rom = ROM_ZH.read_bytes()
    print(f"  ROM 文件前 0xC0: {rom[:0xC0].hex(' ')}")
    print(f"\n  若上面 [ROMHEAD] 与此一致 ⇒ emu:readRange 读的是真内存")
    print(f"  若不一致            ⇒ 读法有问题，需先修工具")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
