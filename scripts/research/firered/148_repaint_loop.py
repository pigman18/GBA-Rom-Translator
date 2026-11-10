#!/usr/bin/env python3
"""调研(148) 让 Lua 反复重绘菜单，配合 watchpoint 抓字形来源。

═══════════════════════════════════════════════════════════════════════════
【(147) 的成功与遗留】
═══════════════════════════════════════════════════════════════════════════
✅ 成功：隐藏窗口 + Lua 驱动 + GDB 旁路，三者共存（不抢键盘、不弹窗）
✅ 关键修正：GDB 连上后必须 `continue`，否则 Lua 不跑

❌ 遗留：watchpoint 命中 0 次
   原因：游戏停在菜单后画面静止，字形**早就写进 VRAM 了**，不再重复写。

【解法：让 Lua 反复触发重绘】
 在菜单里上下移动光标 → 每次都重绘屏幕 → 每次都会写 VRAM。
 这样 watchpoint 就有机会命中。

【本脚本】
 Lua 部分：
   ① 读档进菜单
   ② 之后每 60 帧按一次 UP/DOWN（在菜单里移动光标，触发重绘）
   ③ 一直持续到 Python 叫停

 Python 部分：
   ① GDB 连接 → **立即 continue**（关键）
   ② 等 Lua 到菜单
   ③ 下 4 个 VRAM watchpoint
   ④ 持续 continue，每次命中也抓 PC/寄存器/LR
   ⑤ 汇总哪些 PC 在写 VRAM、寄存器里的 ROM 地址

用法：python scripts/research/firered/148_repaint_loop.py
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bot"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402
from winhide import popen_hidden                     # noqa: E402

OUT = ROOT / "work" / "_probe" / "repaint"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


LUA = r'''
local OUT = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A, B, START, DOWN, UP = 1, 2, 8, 128, 64
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
local phase = "boot"
local tick = 0
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
            phase = "menu"
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
        end
        return
    end

    -- 已读档：在菜单里反复上下移动光标，制造重绘
    tick = tick + 1
    if tick % 40 == 0 then
        if (tick / 40) % 2 == 0 then
            setk(UP)
        else
            setk(DOWN)
        end
        hold = 8
        log("[MOVE] f=" .. f .. " " .. (((tick / 40) % 2 == 0) and "UP" or "DOWN"))
    end
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
    print("① 隐藏窗口启动")
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
            # ★ 关键：先 continue
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            print("  [gdb] continue 已发出")

            # 等 Lua 到菜单
            logf = OUT / "drive.log"
            t0 = time.time()
            while time.time() - t0 < 45:
                if logf.exists() and "[PROVE]" in logf.read_text(
                        encoding="utf-8", errors="replace"):
                    break
                try:
                    c.cont(timeout=2.0)
                except GdbError:
                    pass
            print("  [gdb] Lua 已读档，开始下 watchpoint")

            for a in (0x06000000, 0x06004000, 0x06008000, 0x0600C000):
                try:
                    c.cmd(f"Z2,{a:x},2")
                except GdbError:
                    pass

            # 持续抓
            while not stop["v"] and len(hits) < 300:
                try:
                    why = c.cont(timeout=1.2)
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
                             "r": vals[:8], "rom": rom_ptrs,
                             "why": str(why)})
                if len(hits) % 20 == 1:
                    print(f"  [gdb] 命中 {len(hits)}  PC=0x{vals[15]:08X}")
            c.close()
        except Exception as e:
            print(f"  [gdb] 异常: {e}")

    t = threading.Thread(target=gdb_worker, daemon=True)
    t.start()
    t.join(timeout=150)
    stop["v"] = True
    time.sleep(1)

    dl = OUT / "drive.log"
    if dl.exists():
        txt = dl.read_text(encoding="utf-8", errors="replace")
        lines = [l for l in txt.splitlines() if l.strip()]
        print(f"\n② Lua 日志 {len(lines)} 行，末尾 5 行：")
        for l in lines[-5:]:
            print(f"    {l}")

    print("\n" + "=" * 78)
    print("③ 结果")
    print("=" * 78)
    print(f"  watchpoint 命中 {len(hits)} 次")
    if hits:
        pc = Counter(h["pc"] for h in hits)
        print(f"\n  写 VRAM 的 PC：")
        for p, n in pc.most_common(10):
            print(f"    0x{p:08X}  ×{n}")
        lr = Counter(h["lr"] for h in hits)
        print(f"\n  调用者 LR：")
        for p, n in lr.most_common(10):
            print(f"    0x{p:08X}  ×{n}")
        allrom = [a for h in hits for a in h["rom"]]
        c2 = Counter(allrom)
        print(f"\n  寄存器里的 ROM 地址（去重 {len(c2)}）：")
        for a, n in c2.most_common(20):
            print(f"    0x{a:08X}  ×{n}")

    try:
        proc.terminate(); proc.wait(timeout=5)
    except Exception:
        proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
