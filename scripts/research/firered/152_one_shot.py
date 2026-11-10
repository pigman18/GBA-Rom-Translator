#!/usr/bin/env python3
"""调研(152) 合并版：一次启动 mGBA，完成「Lua 驱动 + GDB 抓字形来源」全流程。

═══════════════════════════════════════════════════════════════════════════
【为什么重写成一个脚本】
═══════════════════════════════════════════════════════════════════════════
130–151 号脚本每个都单独启动 mGBA，累积了 20+ 次启动。
其中 `bot/winhide.popen_hidden()` 会起一个 **每 150ms 轮询
ShowWindow(SW_HIDE)** 的守护线程；残留进程叠加后表现为**持续闪屏**。
（用户反馈「闪屏变得离谱」就是这个原因。）

⇒ 本脚本**只启动一次**，且：
   · 用 STARTUPINFO + SW_HIDE 启动（不弹窗）
   · **不起** _keep_hidden 轮询线程（避免闪烁）
   · 所有动作在一次会话里做完
   · finally 里确保 terminate

【已确认的四个前提（前 20 个脚本的成果）】
 E1 mGBA `--gdb` 启动会暂停；**GDB 连上后必须发 continue**，Lua 才会跑
 E2 `--script` 与 `--gdb` 可共存（Lua 按键、GDB 旁路观察）
 E3 GDB stub 支持 Z1/Z2/Z3/Z4（hw breakpoint / 读写 watchpoint）
 E4 GDB 的 `g` 包是**小端字节序**（之前全解析错，PC 才一直是 0）

【本脚本做的事】
 ① 一次启动：mGBA --script drive.lua --gdb，窗口隐藏
 ② GDB connect → **立即 continue**
 ③ 等 Lua 把游戏带到中文菜单（读它写的 drive.log）
 ④ 在 **EWRAM 字形缓冲** 与 **VRAM charBase** 双管齐下设 watchpoint
 ⑤ 反复命中，用小端正确解析寄存器，收集：
      · 写 VRAM 的 PC（就是「画字」的函数）
      · r0-r7 里的 ROM 地址（就是「字库」的位置）
 ⑥ 汇总并保存命中记录到 hits.json

用法：python scripts/research/firered/152_one_shot.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "oneshot"
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
    """SW_HIDE 启动，**不起**轮询隐藏线程（避免闪屏）。"""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=si,
    )


def parse_regs(g: str) -> list[int] | None:
    """小端解析 g 包。"""
    hp = "".join(ch for ch in g if ch in "0123456789abcdefABCDEF")
    n = len(hp) // 8
    if n < 16:
        return None
    return [int.from_bytes(bytes.fromhex(hp[k * 8:(k + 1) * 8]), "little")
            for k in range(n)]


LUA = r'''
local OUT = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A, B, START = 1, 2, 8
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

    -- 读档后：反复 A / B 切换画面，逼 VRAM 重写（字形会被重新送进 VRAM）
    tick = tick + 1
    local r = tick % 150
    if r == 0 then
        setk(A); hold = 10; log("[A] f=" .. f)
    elseif r == 60 then
        setk(B); hold = 10; log("[B] f=" .. f)
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
    print("[1/5] 启动 mGBA（隐藏，单次）")
    proc = launch_hidden([str(mgba), "--script", str(lua_path),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    hits: list[dict] = []
    stop = {"v": False}
    phase = {"v": "init"}

    def gdb_worker():
        c = None
        try:
            c = GdbClient("127.0.0.1", 2345, timeout=15.0)
            c.connect()

            # E1: 连上后立即 continue，Lua 才会跑
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            print("[2/5] continue 已发出")

            # 等读档完成
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
            else:
                phase["v"] = "timeout-prove"
                return
            print("[3/5] 已读档，设 watchpoint")

            # VRAM charBase 区 + EWRAM 字形缓冲（(141) 抓到的）
            for a in (0x06000000, 0x06004000, 0x06008000, 0x0600C000):
                try:
                    c.cmd(f"Z2,{a:x},2")
                except GdbError:
                    pass
            for a in (0x0200553C, 0x0200653C, 0x020076EC):
                try:
                    c.cmd(f"Z2,{a:x},4")
                except GdbError:
                    pass
            phase["v"] = "watching"
            print("[4/5] watchpoint 就绪，开始收集")

            deadline = time.time() + 90
            while not stop["v"] and time.time() < deadline and len(hits) < 250:
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
                rom_ptrs = [v for v in vals[:13]
                            if 0x08000000 <= v < 0x0A000000]
                hits.append({
                    "why": str(why),
                    "pc": vals[15],
                    "lr": vals[14],
                    "sp": vals[13],
                    "r0": vals[0], "r1": vals[1], "r2": vals[2],
                    "r3": vals[3],
                    "rom": rom_ptrs,
                })
                if len(hits) <= 10 or len(hits) % 25 == 0:
                    print(f"      #{len(hits)} PC=0x{vals[15]:08X} "
                          f"LR=0x{vals[14]:08X} "
                          f"R0=0x{vals[0]:08X} R3=0x{vals[3]:08X}")
        except Exception as e:
            phase["v"] = f"error: {e}"
        finally:
            if c:
                try:
                    c.close()
                except Exception:
                    pass

    t = threading.Thread(target=gdb_worker, daemon=True)
    t.start()
    t.join(timeout=170)
    stop["v"] = True
    time.sleep(1)

    try:
        proc.terminate()
        proc.wait(timeout=6)
    except Exception:
        proc.kill()

    print("\n[5/5] 汇总")
    print(f"  阶段: {phase['v']}")
    print(f"  命中: {len(hits)}")
    (OUT / "hits.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")

    if hits:
        print("\n  写 VRAM/缓冲 的 PC：")
        for p, n in Counter(h["pc"] for h in hits).most_common(12):
            print(f"    0x{p:08X}  x{n}")
        print("\n  调用者 LR：")
        for p, n in Counter(h["lr"] for h in hits).most_common(10):
            print(f"    0x{p:08X}  x{n}")
        roms = Counter(a for h in hits for a in h["rom"])
        print(f"\n  寄存器里的 ROM 地址（去重 {len(roms)}）：")
        for a, n in roms.most_common(25):
            print(f"    0x{a:08X}  x{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
