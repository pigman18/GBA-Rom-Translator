#!/usr/bin/env python3
"""调研(51) 直接调 mGBA 跑汉化版，dump EWRAM，专门看 0x0203F2C0 那张 F7 表。

═══════════════════════════════════════════════════════════════════════════
【为什么绕开 bot/run.py】
═══════════════════════════════════════════════════════════════════════════
run.py 强制要求：
  · 两侧共用同一份 .sav
  · 场景脚本必须调用 prove()（证明存档被加载）
  · origin 与 translated 都要跑

本次只需要**汉化版的 EWRAM 快照**，不需要对照，所以直接起 mGBA 更省事。

═══════════════════════════════════════════════════════════════════════════
【要拿什么】
═══════════════════════════════════════════════════════════════════════════
静态分析结论（㊻/㊼）：
  转码函数 @0x081DB660：
     ldr r7,[pc,#112]  @ 0x081DB6D8 = 0x0203F2C0   ← 汉化改的（原版 0）
     hi = src[1]; ptr = *(0x0203F2C0 + hi*4)
     逐字节复制 *ptr 直到 0xFF

⇒ 抓 0x0203F2C0 起始 1024 字节（256 项 × 4 字节），看这 256 个指针。
  · 若都指向 ROM 里「单字节字符序列」→ 证实「用原版字符拼」
  · 若指向压缩数据/需要解压 → 你的怀疑成立

用法：python scripts/research/firered/51_dump_ewram.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
def find_mgba():
    """必须用 mgba_dev 的构建版：发行版 mGBA-0.10.5 **没有 --script**。"""
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


MGBA = find_mgba()
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
OUT = ROOT / "work" / "_probe" / "ewram"

LUA = r'''
local OUT = os.getenv("EMU_OUT")
local SAVE = os.getenv("EMU_SAVE")

local lg = assert(io.open(OUT .. "/dump.log", "w"), "cannot open log")
local function log(s) lg:write(s .. "\n"); lg:flush() end

local function wr(path, data)
    local f = assert(io.open(path, "wb"), "cannot write " .. path)
    f:write(data); f:close()
end

local function hex(v) return string.format("%08X", v) end

local frame = 0
local dumped = 0

callbacks:add("frame", function()
    frame = frame + 1
    -- 给足时间让游戏加载存档、建立 F7 表
    if frame < 600 then return end

    -- 每 300 帧 dump 一次，共 6 次，覆盖不同界面
    if frame % 300 == 0 and dumped < 6 then
        dumped = dumped + 1
        local tag = OUT .. "/d" .. dumped
        wr(tag .. ".ewram.bin", emu:readRange(0x02000000, 0x40000))
        wr(tag .. ".iwram.bin", emu:readRange(0x03000000, 0x8000))
        wr(tag .. ".vram.bin",  emu:readRange(0x06000000, 0x18000))
        wr(tag .. ".pal.bin",   emu:readRange(0x05000000, 0x400))
        wr(tag .. ".io.bin",    emu:readRange(0x04000000, 0x60))
        emu:screenshot(tag .. ".png")

        -- ★ 直接读 0x0203F2C0 起 1024 字节（F7 表的 256 个指针）
        wr(tag .. ".f7table.bin", emu:readRange(0x0203F2C0, 0x400))
        -- ★ 也读 0x03003E60（字宽函数里的另一个基址）
        wr(tag .. ".base3e60.bin", emu:readRange(0x03003E60, 0x400))

        log(string.format("[D%d] f=%d dispcnt=%04X", dumped, frame,
                          emu:read16(0x04000000)))
    end

    if frame > 2200 then
        log("done f=" .. frame)
        lg:close()
        emu:exit()
    end
end)
'''


def main() -> int:
    if not MGBA.exists():
        print(f"mGBA not found: {MGBA}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        f.unlink()

    lua_path = OUT / "_dump.lua"
    lua_path.write_text(LUA, encoding="utf-8")

    rom = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_SAVE"] = str(SAVE).replace("\\", "/")

    print(f"mGBA   : {MGBA}")
    print(f"ROM    : {rom.name}")
    print(f"OUT    : {OUT}")
    print("启动中（约 2200 帧）…")

    # mGBA 的 --script 参数；存档由 ROM 同名 .sav 自动加载
    # 先把 .sav 复制到 ROM 同目录（mGBA 按 ROM 名找存档）
    rom_copy = OUT / (rom.stem + ".gba")
    shutil.copy2(rom, rom_copy)
    sav_copy = OUT / (rom.stem + ".sav")
    shutil.copy2(SAVE, sav_copy)

    cmd = [str(MGBA), "--script", str(lua_path), str(rom_copy)]
    p = subprocess.Popen(cmd, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        p.wait(timeout=600)
    except subprocess.TimeoutExpired:
        p.kill()
        print("超时，强杀")

    print("\n产出：")
    for f in sorted(OUT.glob("*.bin")):
        print(f"  {f.name}  {f.stat().st_size:,} B")
    lg = OUT / "dump.log"
    if lg.exists():
        print("\n--- dump.log ---")
        print(lg.read_text(encoding="utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
