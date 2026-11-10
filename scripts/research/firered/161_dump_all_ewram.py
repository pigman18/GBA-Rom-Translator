#!/usr/bin/env python3
"""调研(161) 一次性 dump 中文菜单的完整 EWRAM，之后全部离线分析。

═══════════════════════════════════════════════════════════════════════════
【为什么改用这条路】
═══════════════════════════════════════════════════════════════════════════
130–160 一直在「设断点 / watchpoint / 读特定地址」上打转，反复启模拟器，
既慢又折腾环境。而已经掌握的事实足够支撑一次全量抓取：

 E1 (152) 在中文菜单下稳定抓到 DMA 启动点 0x08000DF4，
    R3 = EWRAM 源缓冲（0x020047F0 / 0x020053B0），R0 = 0x80000000
 E2 (141) 在标题画面抓到 EWRAM 缓冲内容 nibble 只有 1/2/3（字形特征）
 E3 汉字墨迹 11×11、三档灰度，字形数据必然是 nibble 1/2/3 为主

⇒ **字形在送进 VRAM 前一定先存在于 EWRAM 的某处。**
   把整块 EWRAM（256KB）一次性 dump 下来，离线就能：
     · 找出所有「nibble 集中在 1/2/3」的区
     · 直接拿这些字节去 ROM 里搜 → 命中即字库源
     · 或者用它们反查「谁复制的」

【本脚本只做一件事：dump】
 一次启动（窗口模式 + 隐藏）→ 读档到中文菜单 → dump EWRAM/VRAM/PAL/IWRAM
 → 立刻退出。

 之后所有分析都基于这份快照（脚本 162 起），不再启模拟器。

用法：python scripts/research/firered/161_dump_all_ewram.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "snapshot"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def ensure_windowed() -> None:
    cfg = next(ROOT.glob("tools/mgba_dev/mGBA-build-*/config.ini"), None)
    if cfg and cfg.exists():
        txt = cfg.read_text(encoding="utf-8", errors="replace")
        if "fullscreen=1" in txt:
            cfg.write_text(txt.replace("fullscreen=1", "fullscreen=0"),
                           encoding="utf-8")


def launch_hidden(cmd, cwd, env):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return subprocess.Popen(cmd, cwd=cwd, env=env,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            startupinfo=si)


def main() -> int:
    ensure_windowed()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    # Lua：读档 → 停在中文菜单，并每 300 帧打一次标记（证明还活着）
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
            proved = true
            log("[PROVE] f=" .. f)
            -- 读档瞬间也存一份 EWRAM（早期状态）
            local fp = io.open(OUT .. "/ewram_at_prove.bin", "wb")
            if fp then fp:write(ew); fp:close() end
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
    if f % 300 == 0 then log("[MENU] f=" .. f) end
end)
''', encoding="utf-8")

    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_IDENT"] = SAVE.read_bytes()[:8].hex()

    mgba = find_mgba()
    print("[1/4] 启动（窗口模式 + 隐藏，单次）")
    proc = launch_hidden([str(mgba), "--script", str(lua),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    try:
        c = GdbClient("127.0.0.1", 2345, timeout=20.0)
        c.connect()
        try:
            c.cont(timeout=0.3)
        except GdbError:
            pass

        logf = OUT / "drive.log"
        t0 = time.time()
        while time.time() - t0 < 90:
            if logf.exists() and "[PROVE]" in logf.read_text(
                    encoding="utf-8", errors="replace"):
                break
            try:
                c.cont(timeout=2.0)
            except GdbError:
                pass
        else:
            print("[2/4] **读档超时**")
            return 1
        print("[2/4] 已读档")

        # 再跑一会儿，让菜单完全稳定
        try:
            c.cont(timeout=2.5)
        except GdbError:
            pass

        print("[3/4] dump 全量内存")
        # GDB 单次读长度有限，分块读
        def read_all(addr: int, size: int, chunk: int = 0x1000) -> bytes:
            buf = bytearray()
            for o in range(0, size, chunk):
                n = min(chunk, size - o)
                for attempt in range(4):
                    try:
                        buf.extend(c.read_mem(addr + o, n))
                        break
                    except GdbError:
                        if attempt == 3:
                            buf.extend(b"\x00" * n)
                        time.sleep(0.05)
            return bytes(buf)

        parts = {
            "ewram.bin": (0x02000000, 0x40000),
            "iwram.bin": (0x03000000, 0x8000),
            "vram.bin": (0x06000000, 0x18000),
            "pal.bin": (0x05000000, 0x400),
            "oam.bin": (0x07000000, 0x400),
        }
        for name, (addr, size) in parts.items():
            blob = read_all(addr, size)
            (OUT / name).write_bytes(blob)
            nz = sum(1 for b in blob if b)
            print(f"    {name:<12} {len(blob):>7,} B  非零 {nz:>7,}")

        print("[4/4] 完成")
        c.close()
    except GdbError as e:
        print(f"GDB 错误：{e}")
        return 1
    finally:
        try:
            proc.terminate(); proc.wait(timeout=6)
        except Exception:
            proc.kill()

    print(f"\n快照已存于 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
