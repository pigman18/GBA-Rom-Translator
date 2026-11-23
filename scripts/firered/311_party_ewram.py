#!/usr/bin/env python3
"""火红队伍界面：EWRAM 里的名字串到底是 F7 还是日文？

═══ 为什么要直接抓内存 ═══
静态已证：
  · 原版日文名表 0x203CB8 一个字节没动
  · 汉化新增 412 项指针表 0x0871BFB0 → 各自指向独立中文 F7 串
  · 0x08053358 取名字处把 StringCopy 换成了 0x0810935E（带裁剪的转换器）

但还没回答：
  ① 队伍界面渲染时，喂给 PrintNextChar 的串是 F7 还是日文？
  ② 存档 nickname[10] 里是 F7 还是日文？

本脚本：进队伍界面后 dump 整个 EWRAM(256KB) + IWRAM(32KB)，
离线扫描所有「以 FF 结尾的 F7 串」与「日文名表原样串」，
定位它们落在哪个地址，再对照已知缓冲（0x02021C4C / 0x02022A28）。

用法：python scripts/firered/311_party_ewram.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "ewram311"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"
SW_HIDE = 0


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
local function dump(tag)
    local f = assert(io.open(OUTP .. "/" .. tag .. ".ewram.bin", "wb"))
    f:write(emu:readRange(0x02000000, 0x40000)); f:close()
    f = assert(io.open(OUTP .. "/" .. tag .. ".iwram.bin", "wb"))
    f:write(emu:readRange(0x03000000, 0x8000)); f:close()
    f = assert(io.open(OUTP .. "/" .. tag .. ".vram.bin", "wb"))
    f:write(emu:readRange(0x06000000, 0x18000)); f:close()
    log("[DUMP] " .. tag .. " f=" .. emu:currentFrame())
end
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
    if phase == "down" then phase = "enter"; hold = 16; setk(K.A); wait = 240; return end
    if phase == "enter" then
        log("[PARTY] dc=" .. string.format("%04X", rd16(0x04000000)) .. " f=" .. f)
        dump("party")
        -- 再等 40 帧抓第二份（确认不是瞬时态）
        wait = 40
        phase = "party2"
        return
    end
    if phase == "party2" then
        dump("party2")
        phase = "idle"
        return
    end
end)
'''


def read_mem(c, addr, n, chunk=0x8000):
    out = bytearray()
    while n > 0:
        m = min(chunk, n)
        try:
            r = c.cmd(f"m{addr:x},{m:x}")
        except GdbError:
            break
        r = str(r)
        if r.startswith("E"):
            break
        hp = "".join(ch for ch in r if ch in "0123456789abcdefABCDEF")
        try:
            b = bytes.fromhex(hp)
        except ValueError:
            break
        if not b:
            break
        out += b
        addr += len(b)
        n -= len(b)
    return bytes(out)


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

    # 等 drive.log 出现 [PARTY] 再抓内存
    logp = OUT / "drive.log"
    deadline = time.time() + 200
    while time.time() < deadline:
        if logp.is_file() and "[PARTY]" in logp.read_text(encoding="utf-8", errors="replace"):
            break
        time.sleep(1)
    else:
        print("[!] 驱动力没进队伍界面")
        proc.terminate()
        return 1

    print("[2/4] 已进队伍界面，抓内存")
    try:
        c = GdbClient("127.0.0.1", 2345, timeout=15.0)
        c.connect()
        try:
            c.cont(timeout=0.3)
        except GdbError:
            pass
        # 中断
        try:
            c.cmd("\x03")
        except Exception:   # noqa: BLE001
            pass
        time.sleep(0.5)

        for tag, base, size in (("ewram", 0x02000000, 0x40000),
                                ("iwram", 0x03000000, 0x8000)):
            b = read_mem(c, base, size)
            (OUT / f"{tag}.bin").write_bytes(b)
            print(f"  {tag}: {len(b):,} B")
        c.close()
    except Exception as exc:    # noqa: BLE001
        print(f"[!] {exc}")
    finally:
        try:
            proc.terminate()
        except Exception:       # noqa: BLE001
            pass

    # 离线分析
    print("\n[3/4] 扫描 EWRAM")
    ew = (OUT / "ewram.bin").read_bytes()
    if not ew:
        print("  EWRAM 空，退出")
        return 1

    # ① F7 串（F7 xx xx 三字节组，FF 结尾）
    f7_runs = []
    i = 0
    while i < len(ew) - 3:
        if ew[i] == 0xF7 and 0x01 <= ew[i + 1] <= 0x0A:
            j = i
            cnt = 0
            while j + 2 < len(ew) and ew[j] == 0xF7 and 0x00 <= ew[j + 1] <= 0x0A:
                cnt += 1
                j += 3
            if cnt >= 2 and j < len(ew) and ew[j] == 0xFF:
                f7_runs.append((0x02000000 + i, cnt))
                i = j + 1
                continue
        i += 1
    print(f"  F7 串（≥2 字，FF 结尾）: {len(f7_runs)} 处")
    for a, n in f7_runs[:10]:
        off = a - 0x02000000
        print(f"    0x{a:08X} ({n}字): {ew[off:off+n*3+1].hex(' ')}")

    # ② 日文名表原样串（フシギダネ = 6c 5c 88 91 68）
    jp_pats = {
        "フシギダネ": bytes([0x6C, 0x5C, 0x88, 0x91, 0x68]),
        "フシギソウ": bytes([0x6C, 0x5C, 0x88, 0x5F, 0x53]),
    }
    print("\n  日文名原样出现:")
    for nm, pat in jp_pats.items():
        hits = []
        s = 0
        while True:
            k = ew.find(pat, s)
            if k < 0:
                break
            hits.append(0x02000000 + k)
            s = k + 1
        print(f"    {nm}: {len(hits)} 处 {[hex(x) for x in hits[:6]]}")

    # ③ 已知缓冲内容
    print("\n[4/4] 已知缓冲")
    for name, addr, n in (("0x02021C4C", 0x02021C4C, 48),
                          ("0x02022A28", 0x02022A28, 48),
                          ("0x0203F2C0", 0x0203F2C0, 64)):
        off = addr - 0x02000000
        print(f"  {name}: {ew[off:off+n].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
