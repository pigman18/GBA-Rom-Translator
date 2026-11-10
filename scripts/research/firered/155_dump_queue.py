#!/usr/bin/env python3
"""调研(155) 读出打印命令队列 —— 每项含「源地址」，那就是字形来源。

═══════════════════════════════════════════════════════════════════════════
【(154) 完全解出命令项结构】
═══════════════════════════════════════════════════════════════════════════
四个类型分支的代码模式完全一致：

    ldr  r3,[r1,#0]      ; r3 = [项+0]  = **源地址**
    ldr  r2,[r0,#0]      ; r2 = [项+4]  = **目标地址**
    ldrh r1,[r1,#8]      ; r1 = [项+8]  = **长度**（半字）
    str  r3,[r7,#0]      ; DMA3SAD = r3
    str  r2,[r7,#4]      ; DMA3DAD = r2
    ldr  r0,[pc]         ; DMA 控制字（含类型）
    str  r0,[r7,#8]      ; DMA3CNT，启动

类型对应的 DMA 控制字：
    类型1 → 0x84000000 | (len>>2)   32 位传输
    类型2 → 0x85000000 | (len>>2)   32 位传输（目标递减？）
    类型3 → 0x80000000 | (len>>1)   16 位传输  ★
    类型4 → 0x81000000 | (len>>1)

⇒ **命令项（16 字节）布局：**
      +0x00 u32  源地址（ROM 或 EWRAM）
      +0x04 u32  目标地址（VRAM）
      +0x08 u16  长度
      +0x0A u16  类型（1..4）
      +0x0C u32  额外参数

队列基址 0x030000C8（IWRAM），索引在 0x030000C9。

【本脚本】
 ① 一次启动 mGBA，读档到中文菜单
 ② 读 0x030000C8 起 64 项
 ③ 筛出「源地址在 ROM」的项 → 那是字形数据源
 ④ 对每个源地址，读它的内容，判断是不是字形/压缩块

用法：python scripts/research/firered/155_dump_queue.py
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "queue"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
SW_HIDE = 0


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def launch_hidden(cmd, cwd, env):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return subprocess.Popen(cmd, cwd=cwd, env=env,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            startupinfo=si)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))
    lua = OUT / "drive.lua"
    lua.write_text(r'''
local OUT = os.getenv("EMU_OUT") or "."
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
local logf = assert(io.open(OUT .. "/drive.log", "w"))
local function log(s) logf:write(s .. "\n"); logf:flush() end
local function setk(m) emu:setKeys(m) end
callbacks:add("frame", function()
    local f = emu:currentFrame()
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true; log("[PROVE] f=" .. f)
        end
    end
    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1
        else last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true; hold = 12; setk(A)
        end
        return
    end
    if f % 600 == 0 then log("[MENU] f=" .. f) end
end)
''', encoding="utf-8")

    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_IDENT"] = SAVE.read_bytes()[:8].hex()

    mgba = find_mgba()
    print("[启动 mGBA（隐藏，单次）]")
    proc = launch_hidden([str(mgba), "--script", str(lua),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    try:
        c = GdbClient("127.0.0.1", 2345, timeout=15.0)
        c.connect()
        try:
            c.cont(timeout=0.3)
        except GdbError:
            pass

        logf = OUT / "drive.log"
        t0 = time.time()
        while time.time() - t0 < 60:
            if logf.exists() and "[PROVE]" in logf.read_text(
                    encoding="utf-8", errors="replace"):
                break
            try:
                c.cont(timeout=2.0)
            except GdbError:
                pass
        print("[已读档]")

        # 队列基址：0x030000C8。先看开头 64 字节判断布局
        print("\n" + "=" * 78)
        print("① IWRAM 0x03000080..0x03000140（找队列布局）")
        print("=" * 78)
        blk = c.read_mem(0x03000080, 0xC0)
        for o in range(0, 0xC0, 16):
            print(f"  0x{0x03000080+o:08X}: {blk[o:o+16].hex(' ')}")

        # 按不同基址试解析
        print("\n" + "=" * 78)
        print("② 按 16 字节项解析（基址 0x030000C8）")
        print("=" * 78)
        raw = c.read_mem(0x030000C8, 16 * 48)
        print(f"  {'#':>3} {'源':>12} {'目标':>12} {'长度':>6} {'类型':>5} 说明")
        roms = []
        for k in range(48):
            it = raw[k * 16:(k + 1) * 16]
            if len(it) < 16:
                break
            src = int.from_bytes(it[0:4], "little")
            dst = int.from_bytes(it[4:8], "little")
            ln = int.from_bytes(it[8:10], "little")
            ty = int.from_bytes(it[10:12], "little")
            note = []
            if 0x08000000 <= src < 0x0A000000:
                note.append("源=ROM")
                roms.append(src)
            elif 0x02000000 <= src < 0x03000000:
                note.append("源=EWRAM")
            if 0x06000000 <= dst < 0x07000000:
                note.append("目标=VRAM")
            if not note:
                continue
            print(f"  {k:>3} 0x{src:08X} 0x{dst:08X} {ln:>6} {ty:>5} "
                  f"{' '.join(note)}")

        # ── ③ 对 ROM 源读内容 ──────────────────────────────────
        print("\n" + "=" * 78)
        print(f"③ 源地址在 ROM 的项（{len(set(roms))} 个不同地址）")
        print("=" * 78)
        seen = set()
        for src in roms:
            if src in seen:
                continue
            seen.add(src)
            try:
                blob = c.read_mem(src, 32)
            except GdbError:
                continue
            islz = (blob[0] >> 4) == 1
            print(f"  0x{src:08X}  {'★LZ77头' if islz else ''}")
            print(f"      {blob.hex(' ')}")
            if len(seen) >= 15:
                break

        c.close()
    except GdbError as e:
        print(f"GDB 错误：{e}")
    finally:
        try:
            proc.terminate(); proc.wait(timeout=6)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
