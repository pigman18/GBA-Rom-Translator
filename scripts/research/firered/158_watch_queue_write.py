#!/usr/bin/env python3
"""调研(158) 找「谁往队列写」—— 队列在消费时是空的，必须抓填充端。

═══════════════════════════════════════════════════════════════════════════
【(156)(157) 的结论】
═══════════════════════════════════════════════════════════════════════════
 · 0x030000C8 这个队列**在帧边界处是空的**（全 0）
 · 在 0x08000C34（消费入口）断点命中 12 次，但队列读出来还是全 0
 · 读长度没问题（512 字节都能读，之前 E06 是偶发）

⇒ 队列是在**消费函数内部**被边读边清的。
   想看内容，得抓「填充」的那一刻。

【做法：watchpoint 监视队列首项】
 在 0x030000C8 上设写 watchpoint（Z2）。
 一旦有人写它，立刻中断 → 那时队列刚被填充 → 读出来就是完整的。

 这是最直接的办法。

【注意】
 队列每帧都被填充，watchpoint 会频繁命中。
 命中后立刻读队列，若有效就保存，然后继续。

用法：python scripts/research/firered/158_watch_queue_write.py
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

OUT = ROOT / "work" / "_probe" / "queue5"
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


def parse_regs(g: str) -> list[int] | None:
    hp = "".join(ch for ch in g if ch in "0123456789abcdefABCDEF")
    n = len(hp) // 8
    if n < 16:
        return None
    return [int.from_bytes(bytes.fromhex(hp[k * 8:(k + 1) * 8]), "little")
            for k in range(n)]


def main() -> int:
    ensure_windowed()
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
    print("[1/5] 启动（窗口模式 + 隐藏）")
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
        print("[2/5] 已读档")

        print("[3/5] 在队列 0x030000C8 设写 watchpoint")
        ok = False
        try:
            r = c.cmd("Z2,030000C8,4")
            ok = r.startswith("OK")
            print(f"    Z2 结果: {r[:20]}")
        except GdbError as e:
            print(f"    失败: {e}")

        if not ok:
            print("    改用 2 字节")
            try:
                r = c.cmd("Z2,030000C8,2")
                print(f"    Z2: {r[:20]}")
            except GdbError as e:
                print(f"    失败: {e}")

        print("[4/5] 等写入命中，命中就读队列")
        saved = 0
        for i in range(40):
            try:
                why = c.cont(timeout=2.0)
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
            pc, lr = vals[15], vals[14]
            # 立刻读队列
            try:
                raw = c.read_mem(0x030000C8, 0x200)
            except GdbError:
                continue
            n_ok = 0
            lines = []
            for k in range(32):
                it = raw[k * 16:(k + 1) * 16]
                if len(it) < 16:
                    break
                src = int.from_bytes(it[0:4], "little")
                dst = int.from_bytes(it[4:8], "little")
                ln = int.from_bytes(it[8:10], "little")
                ty = int.from_bytes(it[10:12], "little")
                srcok = (0x08000000 <= src < 0x0A000000 or
                         0x02000000 <= src < 0x03000000)
                dstok = 0x06000000 <= dst < 0x07000000
                if not (srcok and dstok):
                    continue
                n_ok += 1
                lines.append(f"      [{k:>2}] 源=0x{src:08X} "
                             f"目标=0x{dst:08X} len={ln:>5} type={ty}")
                if 0x08000000 <= src < 0x0A000000 and n_ok <= 4:
                    try:
                        blob = c.read_mem(src, 24)
                        islz = (blob[0] >> 4) == 1
                        lines.append(f"           内容 {blob.hex(' ')}"
                                     f"{'  ★LZ77' if islz else ''}")
                    except GdbError:
                        pass
            if n_ok:
                saved += 1
                print(f"\n  === 命中 {saved}  PC=0x{pc:08X} "
                      f"LR=0x{lr:08X}  有效项 {n_ok} ===")
                for l in lines[:14]:
                    print(l)
            if saved >= 3:
                break

        print(f"\n[5/5] 抓到 {saved} 次有效队列")
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
