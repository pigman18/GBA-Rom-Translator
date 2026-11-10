#!/usr/bin/env python3
"""调研(147) 正确做法：隐藏窗口 + Lua 驱动按键 + GDB 旁路抓取。

═══════════════════════════════════════════════════════════════════════════
【(146) 错在哪】
═══════════════════════════════════════════════════════════════════════════
两个严重问题：
 ① **接管键盘 + 全屏** —— 我用 SendKeys + SetForegroundWindow 抢用户输入，
    还让 mGBA 窗口跳到前台。完全不该这么做。
 ② **本该由 Lua 按键** —— 项目已有 bot 体系（emu_run / Lua），
    我却绕开它去模拟键盘。

【真正的技术根因（(144) 那次 Lua 为什么不跑）】
 mGBA 用 `--gdb` 启动时，模拟器**停在暂停状态**等 GDB 客户端。
 此时 Lua 的 frame 回调根本不执行。
 ⇒ **GDB 连上后必须发 `continue`**，模拟器才会跑，Lua 才有机会执行。

 (144) 我连上 GDB 后只 read_mem，没 continue ⇒ Lua 永远不动。
 (145)(146) 我又没用 Lua，改用键盘 ⇒ 抢输入、全屏，是我做错了。

【正确方案】
 ① 用 `bot/winhide.popen_hidden()` 启动 mGBA（窗口隐藏，不抢焦点）
 ② 同一个进程同时带 `--script drive.lua --gdb`
 ③ Lua 负责：读档 → 按键 → 停在中文菜单（有自己的状态机）
 ④ Python：GDB 连上 → **立即 continue**（关键！）→ Lua 开始跑
 ⑤ 等 Lua 把游戏带到菜单（读它写的 log 判断）
 ⑥ 下 watchpoint，继续 continue，抓「写 VRAM」的 PC 与 ROM 源

这样：不抢键盘、不弹窗、按键交给 Lua。

用法：python scripts/research/firered/147_headless_lua_gdb.py
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bot"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402
from winhide import popen_hidden, wait_hidden        # noqa: E402

OUT = ROOT / "work" / "_probe" / "headless"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


# Lua：读档 → 停在中文菜单（继续游戏那个界面），之后不再动作
LUA = r'''
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
    if hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0) end
        return
    end

    if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            log("[PROVE] f=" .. f)
        end
    end

    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1
        else last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true
            hold = 12
            setk(A)
            log("[PRESS] dc=" .. string.format("%04X", dc) .. " f=" .. f)
        end
        return
    end

    -- 已读档：停在菜单，不再按键（等 GDB 抓）
    if f % 300 == 0 then log("[MENU] f=" .. f) end
end)
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))
    lua_path = OUT / "drive.lua"
    lua_path.write_text(LUA, encoding="utf-8")

    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_IDENT"] = SAVE.read_bytes()[:8].hex()

    mgba = find_mgba()
    print("① 隐藏窗口启动 mGBA（--script + --gdb）")
    proc = popen_hidden([str(mgba), "--script", str(lua_path),
                         "--gdb", str(rom_copy)],
                        cwd=str(OUT), env=env)
    time.sleep(5)

    hits = []
    stop = {"v": False}

    def gdb_worker():
        try:
            c = GdbClient("127.0.0.1", 2345, timeout=15.0)
            c.connect()
            print("  [gdb] 已连接")

            # ★★ 关键：先 continue，让模拟器跑起来，Lua 才会执行
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            print("  [gdb] 已发出 continue（Lua 现在能跑了）")

            # 等 Lua 把游戏带到菜单
            logf = OUT / "drive.log"
            t0 = time.time()
            while time.time() - t0 < 40:
                if logf.exists() and "[MENU]" in logf.read_text(
                        encoding="utf-8", errors="replace"):
                    print("  [gdb] Lua 已到菜单")
                    break
                # 保持模拟器运行
                try:
                    c.cont(timeout=2.0)
                except GdbError:
                    pass
            else:
                print("  [gdb] 等菜单超时")

            # 现在下 watchpoint
            for a in (0x06000000, 0x06004000, 0x06008000, 0x0600C000):
                try:
                    c.cmd(f"Z2,{a:x},2")
                except GdbError:
                    pass
            print("  [gdb] watchpoint 已设（4 个 VRAM 地址）")

            while not stop["v"]:
                try:
                    why = c.cont(timeout=1.5)
                except GdbError:
                    continue
                if "watch" not in str(why):
                    continue
                try:
                    regs = c.cmd("g")
                except GdbError:
                    continue
                hp = "".join(ch for ch in regs
                             if ch in "0123456789abcdefABCDEF")[:68]
                if len(hp) < 68:
                    continue
                try:
                    raw = bytes.fromhex(hp)
                except ValueError:
                    continue
                vals = [int.from_bytes(raw[k * 4:(k + 1) * 4], "little")
                        for k in range(16)]
                rom_ptrs = [v for v in vals[:8]
                            if 0x08000000 <= v < 0x0A000000]
                hits.append({"pc": vals[15], "lr": vals[14],
                             "r": vals[:8], "rom": rom_ptrs})
                if len(hits) % 10 == 1:
                    print(f"  [gdb] 命中 {len(hits)} 次  "
                          f"PC=0x{vals[15]:08X}  ROM={len(rom_ptrs)}")
            c.close()
        except Exception as e:
            print(f"  [gdb] 异常: {e}")

    t = threading.Thread(target=gdb_worker, daemon=True)
    t.start()

    # 等 worker 完成或超时
    t.join(timeout=120)
    stop["v"] = True
    time.sleep(1)

    dl = OUT / "drive.log"
    if dl.exists():
        txt = dl.read_text(encoding="utf-8", errors="replace")
        lines = [l for l in txt.splitlines() if l.strip()]
        print(f"\n② Lua 日志（{len(lines)} 行），末尾 6 行：")
        for l in lines[-6:]:
            print(f"    {l}")

    print("\n" + "=" * 78)
    print("③ watchpoint 结果")
    print("=" * 78)
    print(f"  命中 {len(hits)} 次")
    from collections import Counter
    pc = Counter(h["pc"] for h in hits)
    print(f"  命中的 PC：")
    for p, n in pc.most_common(8):
        print(f"    0x{p:08X}  ×{n}")
    allrom = [a for h in hits for a in h["rom"]]
    c2 = Counter(allrom)
    print(f"\n  寄存器里的 ROM 地址（去重 {len(c2)}）：")
    for a, n in c2.most_common(15):
        print(f"    0x{a:08X}  ×{n}")

    try:
        proc.terminate(); proc.wait(timeout=5)
    except Exception:
        proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
