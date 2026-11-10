#!/usr/bin/env python3
"""调研(154) 追到打印入口的命令队列：0x030000C8 的 16 字节项。

═══════════════════════════════════════════════════════════════════════════
【(153) 找到打印入口了】
═══════════════════════════════════════════════════════════════════════════
0x08000C34 是**每帧执行**的绘制主函数，内部是一个**命令队列消费者**：

    8000c4e: ldr  r1,[pc,#100]  → 0x030000C8   ← 命令数组基址（IWRAM）
    8000c50: ldr  r2,[pc,#100]  → 0x030000C9   ← 当前索引（字节）
    8000c52: ldrb r0,[r2,#0]    ; 索引
    8000c54: lsls r0,r0,#4      ; **×16 = 每项 16 字节**
    8000c56: adds r0,r0,r1      ; 项地址 = base + idx*16
    8000c58: ldrh r0,[r0,#8]    ; [项+8]
    8000c5c: cmp  r0,#0 / bne    ; 为 0 就退出
    8000c9e: ldrh r0,[r1,#10]   ; [项+10] = **命令类型**
    8000ca0: cmp  r0,#2 → 0x08000D14   (类型 2)
    8000ca8: cmp  r0,#1 → 0x08000CD0   (类型 1)
    8000cc4: cmp  r0,#3 → 0x08000D80   (类型 3) ★
    8000ccc: cmp  r0,#4 → 0x08000DCC   (类型 4)

而 (152) 抓到的写入点 0x08000DF4 正落在 **0x08000D80 这个类型 3 分支**里！
⇒ **类型 3 = 「把字形数据送到 VRAM」**

【本脚本】
 ① 反汇编 0x08000CD0 / 0x08000D14 / 0x08000D80 / 0x08000DCC（四个类型分支）
 ② 一次启动 mGBA，读 IWRAM 0x030000C8 处的命令队列
 ③ 解析每项 16 字节，看类型 3 的项里有什么（应该含字形指针或坐标）

用法：python scripts/research/firered/154_command_queue.py
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "cmdq"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
BASE = 0x08000000
TMP = ROOT / "work" / "_probe" / "dis"
SW_HIDE = 0


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def dis(rom: bytes, addr: int, size: int = 0x80) -> list[str]:
    off = addr - BASE
    TMP.mkdir(parents=True, exist_ok=True)
    b, e = TMP / "q.bin", TMP / "q.elf"
    b.write_bytes(rom[off:off + size])
    subprocess.run(["arm-none-eabi-objcopy", "-I", "binary", "-O",
                    "elf32-littlearm", "-B", "arm",
                    "--rename-section", ".data=.text", str(b), str(e)],
                   capture_output=True)
    r = subprocess.run(["arm-none-eabi-objdump", "-d",
                        "--adjust-vma=" + hex(addr), "-M", "force-thumb",
                        str(e)], capture_output=True, text=True)
    return [ln.rstrip() for ln in r.stdout.splitlines()
            if "file format" not in ln and "Disassembly" not in ln and ln.strip()]


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
    rom = ROM.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()

    print("=" * 78)
    print("① 四个类型分支")
    print("=" * 78)
    for name, addr in (("类型1", 0x08000CD0), ("类型2", 0x08000D14),
                       ("类型3", 0x08000D80), ("类型4", 0x08000DCC)):
        print(f"\n  ---- {name}  0x{addr:08X} ----")
        for ln in dis(rom, addr, 0x60):
            print("    " + ln)

    # ── ② 启动读命令队列 ──────────────────────────────────────
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
    print("\n[启动 mGBA（隐藏，单次）]")
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

        print("\n" + "=" * 78)
        print("② 读命令队列 base = 0x030000C8")
        print("=" * 78)
        base_mem = c.read_mem(0x030000C8, 16)
        print(f"  基址附近 16 字节: {base_mem.hex(' ')}")
        # 结构：0x030000C8 是数组本身（别人取址），索引在 0x030000C9？
        # 反汇编说：r1=0x030000C8（数组基址）、r2=0x030000C9（索引指针）
        # 那 r2 指向的字节是索引；数组从 0x030000C8 开始
        idx = base_mem[1] if len(base_mem) > 1 else 0
        print(f"  推测索引 = {idx}")

        # 试着从 0x030000C8 起读一段，按 16 字节项解析
        raw = c.read_mem(0x030000C8, 16 * 32)
        print(f"\n  从 0x030000C8 起 32 项（每项 16 B）：")
        print(f"  {'#':>3} {'+0':>10} {'+4':>10} {'+8':>6} {'+10':>6} {'+12':>8}")
        for k in range(32):
            it = raw[k * 16:(k + 1) * 16]
            if len(it) < 16:
                break
            w0 = int.from_bytes(it[0:4], "little")
            w1 = int.from_bytes(it[4:8], "little")
            h8 = int.from_bytes(it[8:10], "little")
            h10 = int.from_bytes(it[10:12], "little")
            h12 = int.from_bytes(it[12:14], "little")
            tag = ""
            if 0x08000000 <= w0 < 0x0A000000:
                tag += " w0=ROM"
            if 0x08000000 <= w1 < 0x0A000000:
                tag += " w1=ROM"
            print(f"  {k:>3} 0x{w0:08X} 0x{w1:08X} {h8:>6} {h10:>6} "
                  f"0x{h12:04X}{tag}")

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
