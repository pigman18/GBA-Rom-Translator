"""调研(302) 用 GDB 在 8 个取字形函数上设断点 —— 直接看队伍界面调用哪一个。

═══ 方法（用户指定的正确路径）═══
不再看截图、不再猜页表。
已经反汇编出 8 个取字形函数（decode16 的调用者）：

    0x080062B4   页表 0x081CEDF4   宽8 高0x0C
    0x08006304   页表 0x081D2DF4   宽8 高0x10
    0x08006354   页表 0x081D6DF4   宽WIDTH 高0x0C
    0x08006418   页表 0x081D6DF4
    0x080064B8   页表 0x081DEF0C / 0x081E6F0C
    0x0800657C   页表 0x081E7024 / 0x081EF024
    0x08006640   页表 0x081EF13C   宽8 高0x0C
    0x08152D64   页表 0x0843D744 / 0x08416B40
  + 0x081DB3EE   页表 0x08B74000（汉化新增）

在这些地址上全部设断点，让游戏走到队伍界面，**看哪个函数被命中**。
命中时读 r0（码位），就知道实际用了哪套。

═══ 为什么这次不会像 178 那样失败 ═══
178 设的是「每帧绘制分发 0x08000C34」，那函数每帧都跑，命中太密导致
一直停、Lua 走不动。

这 8 个是**按字调用的取字形函数**，只在真正画字时命中。
而且只取字形、不画，命中频率低得多。

用法：python scripts/research/firered/302_gdb_break_glyphfns.py
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

OUT = ROOT / "work" / "_probe" / "gdb302"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
SW_HIDE = 0

# 要监控的取字形函数
TARGETS = {
    0x080062B4: "fn_62B4 tbl_081CEDF4 w8 h12",
    0x08006304: "fn_6304 tbl_081D2DF4 w8 h16",
    0x08006354: "fn_6354 tbl_081D6DF4 WIDTH h12",
    0x08006418: "fn_6418 tbl_081D6DF4",
    0x080064B8: "fn_64B8 tbl_081DEF0C/081E6F0C",
    0x0800657C: "fn_657C tbl_081E7024/081EF024",
    0x08006640: "fn_6640 tbl_081EF13C w8 h12",
    0x08152D64: "fn_152D64 tbl_0843D744/08416B40",
    0x081DB3EE: "fn_1DB3EE tbl_08B74000 (汉化新增)",
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


def parse_regs(g: str):
    hp = "".join(ch for ch in g if ch in "0123456789abcdefABCDEF")
    n = len(hp) // 8
    if n < 16:
        return None
    return [int.from_bytes(bytes.fromhex(hp[k * 8:(k + 1) * 8]), "little")
            for k in range(n)]


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

local phase = "await_title"
local hold, wait = 0, 0
local dc_n = 0
local bn = 0
local tick = 0

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
        if dc_is(0x9F40, 10) then phase = "a1"; hold = 16; setk(K.A); return end
        return
    end
    if phase == "a1" then phase = "await_menu"; return end
    if phase == "await_menu" then
        if dc_is(0x3140, 8) then phase = "up"; hold = 10; setk(K.UP); wait = 25; return end
        return
    end
    if phase == "up" then phase = "a2"; hold = 16; setk(K.A); wait = 80; return end
    if phase == "a2" then
        if dc_is(0x7F60, 20) then phase = "press_b"; bn = 0; return end
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
    -- 到队伍界面后：反复上下移动，持续触发重绘（名字/HP 都会重画）
    if phase == "watch" then
        tick = tick + 1
        local r = tick % 50
        if r == 1 then setk(K.DOWN); hold = 4
        elseif r == 15 then setk(K.UP); hold = 4
        end
        if tick % 300 == 0 then
            log("[WATCH] f=" .. f .. " tick=" .. tick)
        end
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
    print(f"[1/6] 启动 mGBA: {mgba.name}")
    proc = launch_hidden([str(mgba), "--script", str(lua_path),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    hits: list[dict] = []
    phase = {"v": "init"}
    stop = {"v": False}

    def gdb_worker():
        c = None
        try:
            c = GdbClient("127.0.0.1", 2345, timeout=15.0)
            c.connect()
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            print("[2/6] continue，等 Lua 进队伍界面")

            # ★ 立即设断点（游戏还没跑），这样进队伍时的绘制也能抓到
            set_ok = []
            for addr in TARGETS:
                placed = False
                for kind in ("Z1", "Z0"):
                    try:
                        r = c.cmd(f"{kind},{addr:x},2")
                        if r in ("OK", ""):
                            set_ok.append(addr)
                            placed = True
                            break
                    except GdbError:
                        continue
                if not placed:
                    print(f"     断点 0x{addr:08X} 两种方式都失败")
            print(f"[3/6] 设了 {len(set_ok)}/{len(TARGETS)} 个断点")

            phase["v"] = "watching"
            # 观察循环：continue -> 断住 -> 读寄存器 -> continue
            deadline = time.time() + 150
            while not stop["v"] and time.time() < deadline and len(hits) < 300:
                try:
                    why = c.cont(timeout=1.5)
                except GdbError:
                    continue
                w = str(why).lower()
                if "hwbreak" in w or "break" in w or "t05" in w or "t02" in w:
                    regs = None
                    try:
                        regs = c.read_regs()
                    except GdbError:
                        pass
                    if not regs:
                        continue
                    pc = regs.get("pc", 0)
                    rec = {"why": str(why), "pc": pc, "lr": regs.get("lr", 0),
                           "r0": regs.get("r0", 0), "r1": regs.get("r1", 0),
                           "r2": regs.get("r2", 0), "r3": regs.get("r3", 0)}
                    hits.append(rec)
                    if len(hits) <= 10 or len(hits) % 25 == 0:
                        print(f"      #{len(hits)} PC=0x{pc:08X} "
                              f"r0=0x{rec['r0']:08X}")
            phase["v"] = "done"
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

    print(f"\n[5/6] 阶段={phase['v']}  命中={len(hits)}")
    (OUT / "hits.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")

    if not hits:
        print("[6/6] 无命中 —— 见 drive.log")
        lg = OUT / "drive.log"
        if lg.exists():
            print(lg.read_text(encoding="utf-8", errors="replace")[-1200:])
        return 1

    print("\n[6/6] 按 PC 统计命中（这就是队伍界面实际用的取字形函数）")
    for pc, n in Counter(h["pc"] for h in hits).most_common(20):
        tag = TARGETS.get(pc, "")
        print(f"  PC=0x{pc:08X}  x{n}   {tag}")

    print("\n  命中的 r0（码位）样本：")
    seen = []
    for h in hits:
        if len(seen) < 20 and h["r0"] not in [x[0] for x in seen]:
            seen.append((h["r0"], h["pc"]))
    for r0, pc in seen:
        print(f"    r0=0x{r0:04X}  @PC=0x{pc:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
