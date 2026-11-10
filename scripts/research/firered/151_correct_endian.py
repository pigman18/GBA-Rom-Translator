#!/usr/bin/env python3
"""调研(151) 修字节序后重抓：GDB 的 g 包是**小端字节序**。

═══════════════════════════════════════════════════════════════════════════
【(150) 的关键发现】
═══════════════════════════════════════════════════════════════════════════
g 包 = "00000000 04000000 30310003 ..."（每 8 字符一个寄存器）

按**大端**解释：r1 = 0x04000000（合理，IO 基址）
                r14 = 0xAB040008（不对，不是合法地址）
                r15 = 0xAC080008（不对）

按**小端**解释：r14 的字节 "ab 04 00 08" → 0x080004AB  ← **合法 ROM 地址！**
                r15 的字节 "ac 08 00 08" → 0x080008AC  ← **合法 ROM 地址！**

⇒ **g 包的字节序是小端，我之前全解析错了。**
  这解释了为什么 (149) 里 PC 一直是 0、ROM 地址看起来是 0x08416B10 这种。

【本脚本】
 ① 用**正确的小端解析**读寄存器
 ② 在菜单画面设 watchpoint，抓写 VRAM 的 PC
 ③ 从 PC 反汇编，看它从哪读字形

用法：python scripts/research/firered/151_correct_endian.py
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

OUT = ROOT / "work" / "_probe" / "endian"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def parse_regs(g: str) -> list[int] | None:
    """小端解析 g 包 → 17 或 25 个寄存器值。"""
    hp = "".join(ch for ch in g if ch in "0123456789abcdefABCDEF")
    n = len(hp) // 8
    if n < 16:
        return None
    vals = []
    for k in range(n):
        chunk = bytes.fromhex(hp[k * 8:(k + 1) * 8])
        vals.append(int.from_bytes(chunk, "little"))   # ★ 小端
    return vals


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
local tick = 0
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
    -- 读档后：反复按 A/B 切换画面，制造 VRAM 重写
    tick = tick + 1
    if tick % 120 == 0 then setk(1); hold = 10; log("[A] f=" .. f)
    elseif tick % 120 == 50 then setk(2); hold = 10; log("[B] f=" .. f)
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
            print("  [gdb] 已读档，下 watchpoint")

            for a in (0x06000000, 0x06004000, 0x06008000, 0x0600C000,
                      0x06010000):
                try:
                    c.cmd(f"Z2,{a:x},2")
                except GdbError:
                    pass

            while not stop["v"] and len(hits) < 200:
                try:
                    why = c.cont(timeout=1.2)
                except GdbError:
                    continue
                if "watch" not in str(why):
                    continue
                try:
                    g = c.cmd("g")
                except GdbError:
                    continue
                vals = parse_regs(g)
                if not vals:
                    continue
                pc, lr, sp = vals[15], vals[14], vals[13]
                rom_ptrs = [v for v in vals[:8]
                            if 0x08000000 <= v < 0x0A000000]
                hits.append({"pc": pc, "lr": lr, "sp": sp,
                             "r": vals[:8], "rom": rom_ptrs,
                             "why": str(why)})
                if len(hits) <= 8 or len(hits) % 20 == 0:
                    print(f"  [gdb] #{len(hits)} PC=0x{pc:08X} "
                          f"LR=0x{lr:08X}")
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
    print(f"  命中 {len(hits)}")
    if hits:
        pc = Counter(h["pc"] for h in hits)
        print(f"\n  ★ 写 VRAM 的 PC：")
        for p, n in pc.most_common(15):
            print(f"    0x{p:08X}  ×{n}")
        lr = Counter(h["lr"] for h in hits)
        print(f"\n  调用者 LR：")
        for p, n in lr.most_common(10):
            print(f"    0x{p:08X}  ×{n}")
        roms = Counter(a for h in hits for a in h["rom"])
        print(f"\n  寄存器里的 ROM 地址（去重 {len(roms)}）：")
        for a, n in roms.most_common(20):
            print(f"    0x{a:08X}  ×{n}")

    try:
        proc.terminate(); proc.wait(timeout=5)
    except Exception:
        proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
