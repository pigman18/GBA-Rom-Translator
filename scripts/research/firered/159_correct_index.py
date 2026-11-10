#!/usr/bin/env python3
"""调研(159) 修正地址后读队列：索引在 0x030008C9，不是 0x030000C9。

═══════════════════════════════════════════════════════════════════════════
【(158) 为什么 watchpoint 0 命中】
═══════════════════════════════════════════════════════════════════════════
我重新解码了 0x08000C4E / C50 两处 ldr 的字面量：

    0x08000C4E: ldr r1,[pc,#100] → 0x08000CB4 = **0x030000C8**  （数组基址）
    0x08000C50: ldr r2,[pc,#100] → 0x08000CB8 = **0x030008C9**  ← ★
    0x08000C6C: ldr r7,[pc,#76]  → 0x08000CBC = **0x040000D4**  （DMA3）

之前我把索引地址误读成 0x030000C9（少了 0x800）。

⇒ **队列是环形缓冲**：
     数组 0x030000C8 起，每项 16 字节
     索引 0x030008C9（单字节，读写头）

 0x030008C9 - 0x030000C8 = 0x801 = 2049。
 若每项 16 字节，2049 / 16 ≈ 128 项 + 1 字节索引头
 ⇒ 数组约 128 项（0x030000C8..0x030008C8），索引在末尾 0x030008C9。

【本脚本】
 ① 读 0x030008C9（索引）与 0x030000C8 起 128 项
 ② 按 16 字节解析，找「源在 ROM、目标在 VRAM」的项
 ③ 这些源地址就是字形数据

 ⚠ watchpoint 不设了（之前 0 命中说明写入方式与我想的不同）。
   直接读，多试几帧。

用法：python scripts/research/firered/159_correct_index.py
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

OUT = ROOT / "work" / "_probe" / "queue6"
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

        # 多试几帧，每帧都读索引与队列
        print("[3/4] 读索引 0x030008C9 与队列 0x030000C8")
        best = None
        for trial in range(8):
            try:
                c.cont(timeout=0.35)     # 跑一小段
            except GdbError:
                pass
            try:
                idxmem = c.read_mem(0x030008C0, 16)
                raw = c.read_mem(0x030000C8, 0x800)
            except GdbError as e:
                print(f"  试{trial}: 读失败 {e}")
                continue
            idx = idxmem[9] if len(idxmem) > 9 else -1
            print(f"  试{trial}: idxmem={idxmem.hex(' ')}  索引={idx}")

            n_ok = 0
            lines = []
            for k in range(128):
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
                lines.append((k, src, dst, ln, ty))
            print(f"    有效项 {n_ok}")
            if n_ok and (best is None or n_ok > best[0]):
                best = (n_ok, lines, raw)

        # ── 输出最佳 ─────────────────────────────────────────
        print("\n" + "=" * 78)
        print("[4/4] 最佳结果")
        print("=" * 78)
        if best:
            n_ok, lines, raw = best
            print(f"  有效项 {n_ok}")
            for k, src, dst, ln, ty in lines[:20]:
                tag = "ROM" if 0x08000000 <= src < 0x0A000000 else "EWRAM"
                print(f"    [{k:>3}] 源=0x{src:08X}({tag}) "
                      f"目标=0x{dst:08X} len={ln:>5} type={ty}")
                if tag == "ROM":
                    try:
                        blob = c.read_mem(src, 24)
                        islz = (blob[0] >> 4) == 1
                        print(f"            {blob.hex(' ')}"
                              f"{'  ★LZ77' if islz else ''}")
                    except GdbError:
                        pass
            (OUT / "queue_raw.bin").write_bytes(raw)
        else:
            print("  没找到有效项")
            # 打印队列原始前 64 字节供分析
            try:
                raw = c.read_mem(0x030000C8, 64)
                print(f"  队列前 64 字节: {raw.hex(' ')}")
            except GdbError:
                pass

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
