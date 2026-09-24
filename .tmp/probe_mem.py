#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐个地址探测 mGBA GDB stub 的读能力。"""
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
EXE = ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
PORT = 2345


class RSP:
    def __init__(self, timeout=4.0):
        self.sock = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
        self.sock.settimeout(timeout)

    def _send(self, p: bytes):
        self.sock.sendall(b"$" + p + b"#%02X" % (sum(p) & 0xFF))

    def recv_packet(self) -> bytes:
        buf = bytearray()
        while True:
            c = self.sock.recv(1)
            if not c:
                raise RuntimeError("eof")
            if c == b"$":
                break
        while True:
            c = self.sock.recv(1)
            if not c:
                raise RuntimeError("eof")
            if c == b"#":
                break
            buf += c
        self.sock.recv(2)
        self.sock.sendall(b"+")
        return bytes(buf)

    def cmd(self, p: bytes) -> bytes:
        self._send(p)
        return self.recv_packet()

    def drain(self, t=0.5):
        old = self.sock.gettimeout()
        self.sock.settimeout(t)
        try:
            while True:
                print("  [drain]", self.recv_packet()[:40], flush=True)
        except Exception:
            pass
        finally:
            self.sock.settimeout(old)


def main() -> int:
    log = ROOT / ".tmp" / "probe_mem.out"
    fo = open(log, "wb")
    proc = subprocess.Popen([str(EXE), "-g", "-1", str(ROM)], cwd=str(ROOT),
                            stdin=subprocess.DEVNULL, stdout=fo, stderr=fo,
                            close_fds=True)
    try:
        g = None
        for _ in range(40):
            try:
                g = RSP()
                break
            except OSError:
                time.sleep(0.5)
        if g is None:
            print("stub 未就绪", flush=True)
            return 1
        g.drain()
        g._send(b"c")
        time.sleep(6)
        g.sock.sendall(b"\x03")
        print("interrupt:", g.recv_packet()[:30], flush=True)

        tests = [
            (0x04000000, 4), (0x04000008, 8), (0x04000040, 0x20),
            (0x05000000, 4), (0x05000000, 0x20), (0x05000040, 0x20),
            (0x06000000, 4), (0x06000000, 0x40), (0x06000000, 0x400),
            (0x06010000, 0x40), (0x06018000, 0x40),
            (0x07000000, 4), (0x07000000, 0x40),
            (0x02000000, 4), (0x02000000, 0x400),
            (0x03000000, 4), (0x03000000, 0x400),
            (0x08000000, 4), (0x08000000, 0x400),
            (0x03007F00, 0x40),
        ]
        for addr, n in tests:
            t0 = time.time()
            try:
                r = g.cmd(b"m%x,%x" % (addr, n))
                dt = time.time() - t0
                if r.startswith(b"E"):
                    print(f"0x{addr:08X},{n:#x}: ERR {r[:12]} ({dt:.2f}s)", flush=True)
                else:
                    print(f"0x{addr:08X},{n:#x}: OK {len(r) // 2}B ({dt:.2f}s) "
                          f"{r[:32].decode(errors='replace')}", flush=True)
            except Exception as e:
                print(f"0x{addr:08X},{n:#x}: EXC {type(e).__name__} "
                      f"({time.time() - t0:.2f}s)", flush=True)
                g.sock.close()
                g = RSP()
                g.drain(t=0.3)
        g.sock.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        fo.close()
        print("=== 模拟器输出 ===", flush=True)
        print(log.read_text(encoding="utf-8", errors="replace")[:800] or "(空)",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
