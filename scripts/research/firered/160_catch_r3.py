#!/usr/bin/env python3
"""调研(160) 回到最可靠的证据：在 0x08000DF4 命中瞬间读 R3 指向的 EWRAM。

═══════════════════════════════════════════════════════════════════════════
【为什么回到这条】
═══════════════════════════════════════════════════════════════════════════
(152) 在**中文菜单**下稳定抓到 20 次：
    PC  = 0x08000DF4      ← DMA3 启动点（类型3 分支）
    LR  = 0x0800076B      ← 调用者（0x08000C34 内）
    R0  = 0x80000000      ← DMA 控制字
    R3  = 0x020047F0 / 0x020053B0   ← **DMA 源地址（EWRAM）**

后来我去追「命令队列 0x030000C8」，但那块一直是空的 —— 那条路是歧路
（可能 0x030000C8 是别的结构，或我解码错了）。

⇒ **直接抓住 R3。** 在 0x08000DF4 断点命中时，立即读 R3 指向的 EWRAM，
   那就是**正要送进 VRAM 的数据**。若是字形，说明：
     · 字形在 EWRAM 组装 → 再 DMA 到 VRAM
     · 再追「谁写 EWRAM 0x020047F0」就到 ROM 了

【本脚本】
 ① 一次启动（窗口模式 + 隐藏）
 ② 读档到中文菜单
 ③ 在 0x08000DF4 下断点
 ④ 每次命中：读 R3 指向的 128 字节，判断是不是字形
 ⑤ 若是，再在 R3 地址上设写 watchpoint，抓「谁写它」

用法：python scripts/research/firered/160_catch_r3.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "r3"
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
    print("[1/4] 启动")
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
        print("[2/4] 已读档")

        print("[3/4] 在 0x08000DF4 下断点，命中读 R3")
        c.set_sw_break(0x08000DF4, kind=2)

        samples = []
        for i in range(60):
            try:
                why = c.cont(timeout=1.5)
            except GdbError:
                continue
            try:
                g = c.cmd("g")
            except GdbError:
                continue
            vals = parse_regs(g)
            if not vals:
                continue
            pc, lr = vals[15], vals[14]
            if pc != 0x08000DF4:
                continue
            r3 = vals[3]
            r2 = vals[2]
            if not (0x02000000 <= r3 < 0x03000000):
                continue
            try:
                blob = c.read_mem(r3, 128)
            except GdbError:
                continue
            # nibble 判断
            nz = sum(1 for b in blob for v in (b & 0xF, b >> 4) if v)
            samples.append((r3, r2, blob, nz))
            if len(samples) <= 6:
                print(f"\n  命中 {len(samples)}  R3=0x{r3:08X} "
                      f"(目标VRAM=0x{r2:08X})  非零nibble={nz}/256")
                print(f"    {blob[:64].hex(' ')}")
                # 画前 2 tile
                for t in range(2):
                    tb = blob[t * 32:(t + 1) * 32]
                    if len(tb) < 32:
                        break
                    print(f"    tile{t}:")
                    for y in range(8):
                        row = tb[y * 4:(y + 1) * 4]
                        line = ""
                        for x in range(8):
                            b = row[x // 2]
                            v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                            line += "." if v == 0 else "#"
                        print(f"      {line}")
            if len(samples) >= 20:
                break

        print("\n" + "=" * 78)
        print("[4/4] 汇总")
        print("=" * 78)
        print(f"  采到 {len(samples)} 个样本")
        if samples:
            c3 = Counter(s[0] for s in samples)
            print("  R3（EWRAM 源）分布：")
            for a, n in c3.most_common(10):
                print(f"    0x{a:08X}  x{n}")
            print("\n  各样本 nibble 非零数：")
            for a, tgt, blob, nz in samples[:10]:
                print(f"    R3=0x{a:08X} → VRAM 0x{tgt:08X}  非零 {nz}/256")

            # 保存一个样本
            (OUT / "sample.bin").write_bytes(samples[0][2])
            print(f"\n  已保存样本 sample.bin")
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
