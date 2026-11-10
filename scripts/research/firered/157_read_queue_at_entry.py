#!/usr/bin/env python3
"""调研(157) 在「队列非空」的时刻读它 —— 需要在重绘瞬间抓。

═══════════════════════════════════════════════════════════════════════════
【(156) 的情况】
═══════════════════════════════════════════════════════════════════════════
读 0x030000C8 得到 `00 00 05 00 00 ...`（几乎全 0），说明：
  · 队列**已消费完**（画面静止时队列是空的）
  · 索引字节 = 0x05 可能是「队尾」

而且读 1024 字节时 **GDB 报 E06**（超出 IWRAM 0x03008000 边界）。

⇒ 必须在**队列还有内容**的时候读。队列被 `0x08000C34` 每帧消费，
   消费完就清零。所以要在它刚被填充、还没消费完的那一刻抓。

【做法：在消费函数的入口下断点】
 0x08000C34 是每帧的队列消费入口。
 在它上面下断点 → 命中时队列刚被填充、即将消费 → 立刻读队列！

 这次一定能读到内容。

【注意】
 · 只读 0x030000C8..0x03000400（不越 IWRAM 边界）
 · 一次启动，最后统一清理

用法：python scripts/research/firered/157_read_queue_at_entry.py
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

OUT = ROOT / "work" / "_probe" / "queue3"
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
    si.wShowWindow = SW_HIDE
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

        # ★ 在队列消费函数入口下断点
        print("[3/5] 在 0x08000C34（队列消费入口）下断点")
        c.set_sw_break(0x08000C34, kind=2)

        print("[4/5] 命中后读队列")
        got = 0
        for i in range(12):
            try:
                why = c.cont(timeout=3.0)
            except GdbError:
                continue
            try:
                g = c.cmd("g")
            except GdbError:
                continue
            vals = parse_regs(g)
            if not vals:
                continue
            pc = vals[15]
            if pc != 0x08000C34:
                continue
            print(f"\n  === 命中 #{i} PC=0x{pc:08X} ===")

            # 读队列（不越 IWRAM 边界）
            try:
                raw = c.read_mem(0x030000C8, 0x340)
            except GdbError as e:
                print(f"    读队列失败: {e}")
                continue

            # 先看原始
            print(f"    队列前 32 字节: {raw[:32].hex(' ')}")

            # 解析 16 字节项
            n_ok = 0
            for k in range(52):
                it = raw[k * 16:(k + 1) * 16]
                if len(it) < 16:
                    break
                src = int.from_bytes(it[0:4], "little")
                dst = int.from_bytes(it[4:8], "little")
                ln = int.from_bytes(it[8:10], "little")
                ty = int.from_bytes(it[10:12], "little")
                if src == 0 and dst == 0:
                    continue
                notes = []
                if 0x08000000 <= src < 0x0A000000:
                    notes.append("源=ROM")
                elif 0x02000000 <= src < 0x03000000:
                    notes.append("源=EWRAM")
                if 0x06000000 <= dst < 0x07000000:
                    notes.append("目标=VRAM")
                if not notes:
                    continue
                n_ok += 1
                print(f"      [{k:>2}] 源=0x{src:08X} 目标=0x{dst:08X} "
                      f"len={ln:>5} type={ty} {' '.join(notes)}")
                # ROM 源读内容
                if 0x08000000 <= src < 0x0A000000:
                    try:
                        blob = c.read_mem(src, 24)
                        islz = (blob[0] >> 4) == 1
                        print(f"            内容: {blob.hex(' ')}"
                              f"{'  ★LZ77' if islz else ''}")
                    except GdbError:
                        pass
                if n_ok >= 12:
                    break
            print(f"    有效项 {n_ok}")
            got += 1
            if got >= 3:
                break

        print(f"\n[5/5] 命中并读到队列 {got} 次")
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
