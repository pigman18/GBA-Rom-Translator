#!/usr/bin/env python3
"""Launch mGBA.exe --gdb + battery .sav; soft-enter option; check canvas.

Important: do NOT probe-connect then disconnect — mGBA stub is one-shot.
"""
from __future__ import annotations

import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from util._gba_gdb import RSP  # noqa: E402

ROOT = Path(r"C:\code\GBA-Rom-Translator")
MGBA = ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"
ROM = ROOT / "roms" / "work" / "gdb_b1" / "canvas_test.gba"

GMAIN_CB2 = 0x03001770 + 0x24
CB2_INIT_OPTION = 0x08088675
CANVAS_MAGIC_ADDR = 0x0203FE90
CANVAS_BASE = 0x0203FE98
E6F0 = 0x0202E6F0
MAGIC_OK = 0x31535643


def wait_listening(timeout: float = 25.0) -> bool:
    """Poll without completing a client handshake (netstat-style bind check)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        # Try connect but if we succeed we KEEP it? No — use SO bind scan via
        # attempting connect with very short timeout repeatedly is OK if we
        # immediately upgrade that socket to RSP. So: return True only when
        # we can create RSP (first successful connect is the real client).
        try:
            RSP(port=2345)
            return True
        except OSError:
            time.sleep(0.3)
    return False


def main() -> int:
    for ss in ROM.parent.glob("canvas_test.ss*"):
        ss.unlink()

    proc = subprocess.Popen(
        [str(MGBA), "--gdb", str(ROM)],
        cwd=str(ROM.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    r = None
    try:
        t0 = time.time()
        while time.time() - t0 < 25.0:
            try:
                r = RSP(port=2345)
                break
            except OSError:
                time.sleep(0.3)
        if r is None:
            print("GDB stub never accepted")
            return 3
        r.sock.settimeout(8.0)
        print("RSP connected (first client; boot paused)")

        def u32(a: int) -> int:
            return struct.unpack("<I", r.read_mem(a, 4))[0]

        def u16(a: int) -> int:
            return struct.unpack("<H", r.read_mem(a, 2))[0]

        print("DISPCNT", hex(u32(0x04000000) & 0xFFFF))

        r.cont()
        time.sleep(3.0)
        try:
            print("stop1", r.interrupt())
        except Exception as e:
            print("interrupt1", e)
            # reconnect path not available; try mem anyway
            try:
                r = RSP(port=2345)
                r.sock.settimeout(8.0)
            except OSError:
                pass

        for attempt in range(5):
            try:
                payload = b"M%x,%x:%s" % (
                    GMAIN_CB2,
                    4,
                    struct.pack("<I", CB2_INIT_OPTION).hex().encode("ascii"),
                )
                resp = r.exec(payload)
                print(f"poked option attempt {attempt} -> {resp}")
            except Exception as e:
                print("poke fail", e)
                break
            r.cont()
            time.sleep(2.5)
            try:
                print("stop", r.interrupt())
            except Exception as e:
                print("interrupt", e)
            try:
                magic = u32(CANVAS_MAGIC_ADDR)
                base = u16(CANVAS_BASE)
                span = u16(CANVAS_BASE + 2)
                e6 = u16(E6F0)
            except Exception as e:
                print("read fail", e)
                break
            print(f"try{attempt} magic={magic:08X} base={base} span={span} e6f0={e6}")
            if magic == MAGIC_OK and span == 482:
                print("RESULT: PASS")
                r.close()
                return 0

        print("RESULT: FAIL")
        if r:
            r.close()
        return 1
    finally:
        try:
            proc.terminate()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
