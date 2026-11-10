#!/usr/bin/env python3
"""调研(134) 查 DMA 寄存器 —— 字形搬运的源地址会留在寄存器里。

═══════════════════════════════════════════════════════════════════════════
【为什么这是最直接的路】
═══════════════════════════════════════════════════════════════════════════
GBA 把数据搬进 VRAM 必须用 **DMA** 或 CPU 循环。
若是 DMA，**传输完成后寄存器仍保留最后一次的值**：
    DMA0SAD (0x040000B0)  源地址
    DMA0DAD (0x040000B4)  目标地址
    DMA0CNT (0x040000B8)  长度+控制
    DMA1SAD (0x040000BC)  ...  DMA2 (0x040000C8) ... DMA3 (0x040000D4)

⇒ 只要能读到「最近一次往 VRAM 搬运」的 SAD，就知道字形从 ROM 哪里来！

我之前 dump 的 IO 只有 0x04000000..0x04000060，
**DMA 寄存器在 0x040000B0..0x040000E0，全部漏掉了**。

【本脚本】
 ① 让 bot 走到菜单画面（显示中文）
 ② dump 完整的 IO 区（0x04000000..0x04000100，含 DMA 与 KEYINPUT）
 ③ 解析 DMA 寄存器，看有没有「源=ROM、目标=VRAM」的记录
 ④ 若源地址指向 ROM 某处，那一段就是字形数据

用法：python scripts/research/firered/134_dma_registers.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "dma"
IDENT_HEX = SAVE_FR.read_bytes()[:8].hex()

LUA = r'''
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A = 1
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
local st = 0

local function setk(m) emu:setKeys(m) end
local function save(p, addr, len)
    pcall(function()
        local b = emu:readRange(addr, len)
        local f = assert(io.open(p, "wb")); f:write(b); f:close()
    end)
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

    -- 读档后停在菜单，dump 完整 IO（含 DMA）
    if frame == 700 and st == 0 then
        st = 1
        save(OUT .. "/io_full.bin", 0x04000000, 0x100)
        save(OUT .. "/vram.bin", 0x06000000, 0x18000)
        save(OUT .. "/pal.bin", 0x05000000, 0x400)
        pcall(function() emu:screenshot(OUT .. "/menu.png") end)
        RL(string.format("[DUMP] f=%d dc=%04X", frame,
                         emu:read16(0x04000000)))
        DS_DONE(0, "done")
    end
    if frame > 1200 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    r = run_lua(LUA, OUT, expect_files=["io_full.bin", "menu.png"],
                min_frames=600, rom=ROM_ZH, save=SAVE_FR, timeout=300,
                extra_env={"EMU_IDENT": IDENT_HEX})
    print(r.report())
    print(r.log_text)
    if not r.ok:
        return 1

    io = (OUT / "io_full.bin").read_bytes()

    def u16(o):
        return struct.unpack_from("<H", io, o)[0]

    def u32(o):
        return struct.unpack_from("<I", io, o)[0]

    print("\n" + "=" * 78)
    print("① DMA 寄存器")
    print("=" * 78)
    names = ["DMA0", "DMA1", "DMA2", "DMA3"]
    bases = [0xB0, 0xBC, 0xC8, 0xD4]
    for n, b in zip(names, bases):
        sad = u32(b)
        dad = u32(b + 4)
        cnt = u16(b + 8)
        # 解码
        words = (cnt & 0x3) + 1   # 0=16bit 1=32bit
        length = (cnt >> 0) & 0x3FFF
        if cnt & 0x0400:
            length = length * 2 if (cnt & 0x3) != 1 else length * 4
        src_ctl = (cnt >> 7) & 3
        dst_ctl = (cnt >> 5) & 3
        enable = (cnt >> 15) & 1
        print(f"  {n}SAD = 0x{sad:08X}   {n}DAD = 0x{dad:08X}   "
              f"{n}CNT = 0x{cnt:04X}")
        print(f"       长度={length} 单元  使能={enable} "
              f"源调整={src_ctl} 目标调整={dst_ctl}")
        # 判断是否「ROM → VRAM」
        if 0x08000000 <= sad < 0x0A000000 and 0x06000000 <= dad < 0x07000000:
            print(f"       ★★ 这是 ROM→VRAM 的搬运！源 0x{sad:08X}")
        print()

    print("=" * 78)
    print("② DISPCNT / BGxCNT（用正确地址）")
    print("=" * 78)
    dc = u16(0x00)
    print(f"  DISPCNT = 0x{dc:04X}")
    print(f"    BG0={(dc>>8)&1} BG1={(dc>>9)&1} BG2={(dc>>10)&1} "
          f"BG3={(dc>>11)&1} OBJ={(dc>>12)&1} mode={dc&7}")
    for b in range(4):
        v = u16(0x06 + b * 2)
        cb = ((v >> 2) & 3) * 0x4000
        sb = ((v >> 8) & 0x1F) * 0x800
        print(f"  BG{b}CNT = 0x{v:04X}  charBase=0x{cb:04X} "
              f"screenBase=0x{sb:04X}")

    print("\n" + "=" * 78)
    print("③ 完整 IO 区 hex（0x04000000..0x04000100）")
    print("=" * 78)
    for o in range(0, 0x100, 16):
        print(f"  +0x{o:03X}: {io[o:o+16].hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
