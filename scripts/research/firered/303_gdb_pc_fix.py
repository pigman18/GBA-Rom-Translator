"""调研(303) 修正 GDB 寄存器读取，拿到命中的真实函数地址 + 码位。

═══ 302 的结果 ═══
✓ 断点设成功了（9/9）
✓ 命中 142 次
✓ r0 有真实码位（0x01AC / 0x010E / 0x0084 / 0x00BC ...）
✗ PC 全是 0 —— read_regs() 解析有问题

═══ 本脚本修两件事 ═══
① 用原始 `g` 包自己解析（不依赖 read_regs 的 REG_NAMES 顺序）
   ARM7TDMI 的 g 包顺序：r0..r15, cpsr（16 个 32 位，小端）
   pc = 第 15 个
② 命中时额外读 0x03003E60（宽高），这是最直接的判据
③ 把 (pc, r0, width, height) 全记下来

用法：python scripts/research/firered/303_gdb_pc_fix.py
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

OUT = ROOT / "work" / "_probe" / "gdb303"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
SW_HIDE = 0

TARGETS = {
    0x080062B4: "w8 h12 tbl_081CEDF4",
    0x08006304: "w8 h16 tbl_081D2DF4",
    0x08006354: "WIDTH h12 tbl_081D6DF4",
    0x08006418: "tbl_081D6DF4",
    0x080064B8: "tbl_081DEF0C",
    0x0800657C: "tbl_081E7024",
    0x08006640: "w8 h12 tbl_081EF13C",
    0x08152D64: "tbl_0843D744",
    0x081DB3EE: "tbl_08B74000 (汉化)",
}


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    for pat in ("tools/mGBA-*/mGBA.exe", "tools/**/mGBA.exe"):
        c = sorted(ROOT.glob(pat))
        if c:
            return c[0]
    raise SystemExit("找不到 mGBA.exe")


def launch_hidden(cmd, cwd, env):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return subprocess.Popen(cmd, cwd=cwd, env=env,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            startupinfo=si)


def parse_g(g: str):
    """ARM7TDMI: g 包 = 16 个 u32（r0..r15）+ cpsr，小端。"""
    hp = "".join(ch for ch in str(g) if ch in "0123456789abcdefABCDEF")
    if len(hp) < 16 * 8:
        return None
    regs = {}
    names = [f"r{i}" for i in range(13)] + ["sp", "lr", "pc"]
    for i, nm in enumerate(names):
        regs[nm] = int.from_bytes(bytes.fromhex(hp[i * 8:(i + 1) * 8]), "little")
    if len(hp) >= 17 * 8:
        regs["cpsr"] = int.from_bytes(bytes.fromhex(hp[16 * 8:17 * 8]), "little")
    return regs


LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local K = { A = 1, B = 2, START = 8, UP = 64, DOWN = 128 }
local function setk(m) emu:setKeys(m) end
local function rd16(a)
    local ok, v = pcall(function() return emu:read16(a) end)
    if ok then return v end
    return 0
end
local logf = assert(io.open(OUTP .. "/drive.log", "w"))
local function log(s) logf:write(s .. "\n"); logf:flush() end
local phase, hold, wait, dc_n, bn, tick = "await_title", 0, 0, 0, 0, 0
local function dc_is(want, k)
    local dc = rd16(0x04000000)
    if dc == want then dc_n = dc_n + 1 else dc_n = 0 end
    return dc_n >= (k or 8)
end
callbacks:add("frame", function()
    local f = emu:currentFrame()
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end
    if phase == "await_title" then
        if dc_is(0x9F40, 10) then phase = "a1"; hold = 16; setk(K.A) end
        return
    end
    if phase == "a1" then phase = "await_menu"; return end
    if phase == "await_menu" then
        if dc_is(0x3140, 8) then phase = "up"; hold = 10; setk(K.UP); wait = 25 end
        return
    end
    if phase == "up" then phase = "a2"; hold = 16; setk(K.A); wait = 80; return end
    if phase == "a2" then
        if dc_is(0x7F60, 20) then phase = "press_b"; bn = 0 end
        return
    end
    if phase == "press_b" then
        bn = bn + 1
        if bn > 11 then phase = "open"; hold = 16; setk(K.START); wait = 90; return end
        setk(K.B); hold = 10; wait = 40
        return
    end
    if phase == "open" then phase = "down"; hold = 16; setk(K.DOWN); wait = 40; return end
    if phase == "down" then phase = "enter"; hold = 16; setk(K.A); wait = 220; return end
    if phase == "enter" then
        log("[PARTY] dc=" .. string.format("%04X", rd16(0x04000000)) .. " f=" .. f)
        phase = "watch"
        return
    end
    if phase == "watch" then
        tick = tick + 1
        local r = tick % 50
        if r == 1 then setk(K.DOWN); hold = 4
        elseif r == 15 then setk(K.UP); hold = 4 end
        if tick % 400 == 0 then log("[W] f=" .. f .. " t=" .. tick) end
        return
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

    mgba = find_mgba()
    print(f"[1/5] 启动 {mgba.name}")
    proc = launch_hidden([str(mgba), "--script", str(lua_path),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    hits = []
    phase_v = {"v": "init"}
    stop = {"v": False}

    def worker():
        c = None
        try:
            c = GdbClient("127.0.0.1", 2345, timeout=15.0)
            c.connect()
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            set_ok = []
            for addr in TARGETS:
                for kind in ("Z1", "Z0"):
                    try:
                        r = c.cmd(f"{kind},{addr:x},2")
                        if r in ("OK", ""):
                            set_ok.append(addr)
                            break
                    except GdbError:
                        continue
            print(f"[2/5] 断点 {len(set_ok)}/{len(TARGETS)}")

            deadline = time.time() + 200
            while not stop["v"] and time.time() < deadline and len(hits) < 400:
                try:
                    why = c.cont(timeout=1.5)
                except GdbError:
                    continue
                w = str(why).lower()
                if not any(k in w for k in ("break", "t05", "t02")):
                    continue
                try:
                    raw = c.cmd("g")
                except GdbError:
                    continue
                regs = parse_g(raw)
                if not regs:
                    continue
                # 读宽高
                wh = None
                try:
                    wh = c.read_mem(0x03003E60, 2)
                except GdbError:
                    pass
                w0 = wh[0] if wh and len(wh) >= 2 else None
                h0 = wh[1] if wh and len(wh) >= 2 else None
                rec = {"pc": regs["pc"], "lr": regs["lr"],
                       "r0": regs["r0"], "r1": regs["r1"],
                       "r2": regs["r2"], "r3": regs["r3"],
                       "w": w0, "h": h0, "why": str(why)}
                hits.append(rec)
                if len(hits) <= 8 or len(hits) % 40 == 0:
                    print(f"   #{len(hits)} PC=0x{regs['pc']:08X} "
                          f"r0=0x{regs['r0']:04X} "
                          f"wh={w0},{h0}")
            phase_v["v"] = "done"
        except Exception as e:
            phase_v["v"] = f"err: {e}"
        finally:
            if c:
                try:
                    c.close()
                except Exception:
                    pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=280)
    stop["v"] = True
    time.sleep(1)
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    print(f"\n[3/5] 阶段={phase_v['v']}  命中={len(hits)}")
    (OUT / "hits.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")

    if hits:
        print("\n[4/5] 按 PC 统计：")
        for pc, n in Counter(h["pc"] for h in hits).most_common(20):
            tag = TARGETS.get(pc, "")
            print(f"  0x{pc:08X}  x{n}   {tag}")

        print("\n[5/5] 按 (宽,高) 统计：")
        for wh, n in Counter((h["w"], h["h"]) for h in hits).most_common(10):
            print(f"  宽={wh[0]} 高={wh[1]}  x{n}")
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
