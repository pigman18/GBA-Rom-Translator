#!/usr/bin/env python3
"""调研(149) 先定位「字形在 VRAM 的哪一块」，再监视那一块。

═══════════════════════════════════════════════════════════════════════════
【(148) 为什么还是 0 次】
═══════════════════════════════════════════════════════════════════════════
Lua 跑了 179 条日志（f=9045），在菜单里反复移动光标，但 watchpoint 0 命中。

原因分析：
 · 光标移动只改 **tilemap**（screenBase 区），不改 **charBase**（字形区）
 · 而我监视的是 0x06000000 / 0x4000 / 0x8000 / 0xC000 —— 恰好是 charBase 候选
 · 字形早已在 VRAM，不再重写 ⇒ 自然 0 命中

⇒ 得先知道这一帧字形在哪，再监视「不属于字形的那些地址」，或者干脆
   监视「所有 charBase 候选之外」的地区，或者……
   
**更好的思路：反过来。** 不是监视 VRAM，而是：
   监视 **ROM 里的字形源数据**（若它被读，说明从这里取字）。

 (141) 已经发现 EWRAM 写入时 r0 是 ROM 地址（LZ77 头）。
 那么在**显示中文菜单**时，r0 应该指向**含汉字字形的 LZ77 块**。

⇒ 本脚本：**不需要 watchpoint**，改用更强的：
   在 EWRAM 的字形缓冲（0x0200553C 等）上设写 watchpoint，
   命中的瞬间读 r0 → 那就是 ROM 里的字形压缩块！

 (141) 是在**标题画面**抓的，现在让 Lua 保持**中文菜单**，就能抓到汉字的源。

用法：python scripts/research/firered/149_watch_ewram_in_menu.py
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

OUT = ROOT / "work" / "_probe" / "ewmenu"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"

# (141) 在标题画面抓到的字形缓冲地址（EWRAM）
BUF_ADDRS = [0x0200553C, 0x0200653C, 0x020076EC, 0x0200453C,
             0x02004DCC, 0x020061CC, 0x020069CC, 0x020070BC]


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
local A, START, DOWN, UP = 1, 8, 128, 64
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
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
    -- 已读档：间隔按 A（进入/退出子菜单，制造字形重载）
    tick = tick + 1
    if tick % 90 == 0 then
        setk(A); hold = 10
        log("[A] f=" .. f)
    elseif tick % 90 == 45 then
        setk(0)
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
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            print("  [gdb] continue 已发出")

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

            # 在 EWRAM 字形缓冲上设写监视
            n = 0
            for a in BUF_ADDRS:
                try:
                    r = c.cmd(f"Z2,{a:x},4")
                    if r.startswith("OK"):
                        n += 1
                except GdbError:
                    pass
            print(f"  [gdb] EWRAM 缓冲 watchpoint {n} 个")

            while not stop["v"] and len(hits) < 200:
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
                if len(hits) % 5 == 1:
                    print(f"  [gdb] {len(hits)} 次  "
                          f"PC=0x{vals[15]:08X}  "
                          f"R0=0x{vals[0]:08X}")
            c.close()
        except Exception as e:
            print(f"  [gdb] 异常: {e}")

    t = threading.Thread(target=gdb_worker, daemon=True)
    t.start()
    t.join(timeout=150)
    stop["v"] = True
    time.sleep(1)

    print("\n" + "=" * 78)
    print("② 结果")
    print("=" * 78)
    print(f"  命中 {len(hits)} 次")
    if hits:
        allrom = [a for h in hits for a in h["rom"]]
        c2 = Counter(allrom)
        print(f"\n  ★ 寄存器里的 ROM 地址（去重 {len(c2)}）：")
        for a, n in c2.most_common(30):
            print(f"    0x{a:08X}  ×{n}")
        pc = Counter(h["pc"] for h in hits)
        print(f"\n  写入代码 PC：")
        for p, n in pc.most_common(10):
            print(f"    0x{p:08X}  ×{n}")
    else:
        print("  没命中 —— EWRAM 缓冲地址可能只在标题画面用")

    try:
        proc.terminate(); proc.wait(timeout=5)
    except Exception:
        proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
