#!/usr/bin/env python3
"""火红「名字槽」机制实测：GetMonNickname 类函数到底往缓冲区写什么？

═══ 待验证的三个问题 ═══
① 火红渲染队伍/战斗名字时，喂给 PrintNextChar 的串是 F7 还是日文？
② 存档里的 nickname[10] 写的是 F7 还是日文？
③ 如果渲染是 F7、存档是日文，那转换发生在哪一层？

═══ 已知（静态）═══
0x08053358  species*6 + 0x08203CB8(日文表) → StringCopy → 0x02021C4C
汉化版把该 StringCopy 换成 0x0810935E → bx 0x087C04DD（新扫描/转换器）
0x087C04F6 遍历串，遇 F7 前进 3、FC 查表跳参、FF 返回长度 3/10/17

用法：python scripts/research/firered/310_nick_slot_gdb.py
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

OUT = ROOT / "work" / "_probe" / "gdb310"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
SW_HIDE = 0

# 0x08053358 = 取队伍第 N 只昵称；0x0810935E = 汉化替换的拷贝入口
TARGETS = {
    0x08053358: "GetMonNickname(orig path)",
    0x0810935E: "ZH copy stub",
    0x087C04DC: "ZH converter entry",
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
    hp = "".join(ch for ch in str(g) if ch in "0123456789abcdefABCDEF")
    if len(hp) < 16 * 8:
        return None
    regs = {}
    names = [f"r{i}" for i in range(13)] + ["sp", "lr", "pc"]
    for i, nm in enumerate(names):
        regs[nm] = int.from_bytes(bytes.fromhex(hp[i * 8:(i + 1) * 8]), "little")
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
local phase, hold, wait, dc_n, bn = "await_title", 0, 0, 0, 0
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
        phase = "idle"
        return
    end
end)
'''


def read_mem(c, addr, n):
    try:
        r = c.cmd(f"m{addr:x},{n:x}")
    except GdbError:
        return b""
    r = str(r)
    if r.startswith("E"):
        return b""
    hp = "".join(ch for ch in r if ch in "0123456789abcdefABCDEF")
    try:
        return bytes.fromhex(hp)
    except ValueError:
        return b""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    if SAVE.is_file():
        shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))
    lua_path = OUT / "drive.lua"
    lua_path.write_text(LUA, encoding="utf-8")
    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")

    mgba = find_mgba()
    print(f"[1/4] 启动 {mgba.name}")
    proc = launch_hidden([str(mgba), "--script", str(lua_path),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    hits = []
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
            ok = []
            for addr in TARGETS:
                for kind in ("Z1", "Z0"):
                    try:
                        r = c.cmd(f"{kind},{addr:x},2")
                        if r in ("OK", ""):
                            ok.append(addr)
                            break
                    except GdbError:
                        continue
            print(f"[2/4] 断点 {len(ok)}/{len(TARGETS)}")

            deadline = time.time() + 240
            while not stop["v"] and time.time() < deadline and len(hits) < 60:
                try:
                    why = c.cont(timeout=1.5)
                except GdbError:
                    continue
                if not str(why).startswith(("T", "S")):
                    continue
                try:
                    g = c.cmd("g")
                except GdbError:
                    continue
                regs = parse_g(g)
                if not regs:
                    continue
                pc = regs["pc"] & ~1
                # 只在目标点上记
                if pc not in TARGETS:
                    continue
                r0, r1, r2 = regs["r0"], regs["r1"], regs["r2"]
                rec = {"pc": pc, "r0": r0, "r1": r1, "r2": r2,
                       "lr": regs["lr"], "sp": regs["sp"]}
                # 读源串（r1 通常是源指针）与目标缓冲
                for tag, addr, n in (("src", r1, 32), ("dst", r0, 32),
                                     ("buf1", 0x02021C4C, 32),
                                     ("buf2", 0x02022A28, 32)):
                    if 0x02000000 <= addr < 0x04000000 or 0x08000000 <= addr < 0x0A000000:
                        rec[tag] = read_mem(c, addr, n).hex(" ")
                hits.append(rec)
                if len(hits) % 5 == 0:
                    print(f"  hit {len(hits)} pc=0x{pc:08X}")
        except Exception as exc:      # noqa: BLE001
            print(f"[!] {exc}")
        finally:
            stop["v"] = True
            if c:
                try:
                    c.close()
                except Exception:     # noqa: BLE001
                    pass

    import threading
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=280)
    try:
        proc.terminate()
    except Exception:                 # noqa: BLE001
        pass

    print(f"\n[3/4] 命中 {len(hits)} 条")
    # 按 pc 分组统计
    from collections import Counter
    cnt = Counter(h["pc"] for h in hits)
    for pc, n in cnt.items():
        print(f"  0x{pc:08X} ({TARGETS[pc]}): {n}")
    print("\n[4/4] 前 8 条样本")
    for h in hits[:8]:
        print(f"\n  pc=0x{h['pc']:08X} r0=0x{h['r0']:08X} r1=0x{h['r1']:08X} r2={h['r2']}")
        for k in ("src", "buf1", "buf2"):
            if k in h:
                print(f"    {k}: {h[k]}")
    (OUT / "hits.json").write_text(
        __import__("json").dumps(hits, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
