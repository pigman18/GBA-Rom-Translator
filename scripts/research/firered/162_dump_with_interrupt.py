#!/usr/bin/env python3
"""调研(162) 修正：读内存前必须先「中断」模拟器（发 Ctrl-C 0x03）。

═══════════════════════════════════════════════════════════════════════════
【(161) 为什么全 0】
═══════════════════════════════════════════════════════════════════════════
`c.cont(timeout=2.5)` 超时后，**模拟器仍在运行**。
GDB 协议规定：target running 时不能读内存，`m` 包会失败。
我的 read_all 里 4 次重试失败后就填 0 ⇒ 全 0。

【正确做法】
 读内存前先发 **Ctrl-C（0x03）** 让模拟器停住：
   socket.sendall(b"\x03")
   → stub 回 `T05...` → 此时 target 是暂停的 → 可以安全读

 GdbClient 没有 interrupt 方法，本脚本自己实现：
   · 直接用 c.sock 发 0x03
   · 用 c._recv_packet() 收停机应答

【本脚本】
 一次启动 → 读档到中文菜单 → Ctrl-C 中断 → dump 全部内存 → 退出
 之后 163 起全部离线分析。

用法：python scripts/research/firered/162_dump_with_interrupt.py
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "snapshot2"
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


def interrupt(c: GdbClient) -> str:
    """发 Ctrl-C 让 target 停下，返回停机应答。"""
    assert c.sock
    c.sock.settimeout(10.0)
    try:
        # 先清掉可能残留的 ACK
        c.sock.sendall(b"\x03")
        # stub 会回一个 T05... 包
        for _ in range(20):
            b = c._recv_byte()
            if b == ord("$"):
                c._buf.insert(0, b)
                pkt = c._recv_packet()
                return pkt
            # 跳过 + / - / 其他
        return ""
    except Exception as e:
        raise GdbError(f"中断失败: {e}") from e
    finally:
        try:
            c.sock.settimeout(c.timeout)
        except Exception:
            pass


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
    if f % 300 == 0 then log("[MENU] f=" .. f) end
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

    rc = 0
    try:
        c = GdbClient("127.0.0.1", 2345, timeout=20.0)
        c.connect()
        try:
            c.cont(timeout=0.3)
        except GdbError:
            pass

        logf = OUT / "drive.log"
        t0 = time.time()
        while time.time() - t0 < 90:
            if logf.exists() and "[PROVE]" in logf.read_text(
                    encoding="utf-8", errors="replace"):
                break
            try:
                c.cont(timeout=2.0)
            except GdbError:
                pass
        else:
            print("[2/5] 读档超时")
            rc = 1
            raise SystemExit
        print("[2/5] 已读档")

        # 让画面稳定
        try:
            c.cont(timeout=2.5)
        except GdbError:
            pass

        print("[3/5] Ctrl-C 中断 target")
        try:
            why = interrupt(c)
            print(f"    停机应答: {why[:60]}")
        except GdbError as e:
            print(f"    中断失败: {e}")
            rc = 1
            raise SystemExit

        print("[4/5] dump 全部内存")
        def read_all(addr: int, size: int, chunk: int = 0x1000) -> bytes:
            buf = bytearray()
            bad = 0
            for o in range(0, size, chunk):
                n = min(chunk, size - o)
                got = None
                for _ in range(3):
                    try:
                        got = c.read_mem(addr + o, n)
                        break
                    except GdbError:
                        time.sleep(0.05)
                if got is None:
                    bad += 1
                    buf.extend(b"\x00" * n)
                else:
                    buf.extend(got)
            if bad:
                print(f"      （{bad} 个块读取失败）")
            return bytes(buf)

        for name, addr, size in (
            ("ewram.bin", 0x02000000, 0x40000),
            ("iwram.bin", 0x03000000, 0x8000),
            ("vram.bin", 0x06000000, 0x18000),
            ("pal.bin", 0x05000000, 0x400),
            ("oam.bin", 0x07000000, 0x400),
        ):
            blob = read_all(addr, size)
            (OUT / name).write_bytes(blob)
            nz = sum(1 for b in blob if b)
            print(f"    {name:<12} {len(blob):>7,} B  非零 {nz:>7,}")

        print("[5/5] 完成")
        c.close()
    except SystemExit:
        pass
    except GdbError as e:
        print(f"GDB 错误：{e}")
        rc = 1
    finally:
        try:
            proc.terminate(); proc.wait(timeout=6)
        except Exception:
            proc.kill()

    print(f"\n快照目录：{OUT}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
