#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""暂停状态下按固定顺序读一串 (addr,size)，定位 mGBA stub 的失败点。"""
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
EXE = ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
PORT = 2345

TESTS = [
    (0x04000000, 4),
    (0x04000004, 4),
    (0x04000008, 4),
    (0x0400000C, 4),
    (0x04000010, 4),
    (0x04000020, 4),
]


def main():
    state = sys.argv[1] if len(sys.argv) > 1 else "-"
    cmd = [str(EXE), "-g", "-1"]
    if state != "-":
        cmd += ["-t", state]
    cmd.append(str(ROM))
    log = ROOT / ".tmp" / "probe_seq.out"
    fo = open(log, "wb")
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                            stdout=fo, stderr=fo, close_fds=True)
    try:
        s = None
        for _ in range(40):
            try:
                s = socket.create_connection(("127.0.0.1", PORT), timeout=6)
                break
            except OSError:
                time.sleep(0.5)
        if s is None:
            print("stub 未就绪")
            return 1
        s.settimeout(4)

        def recv():
            buf = bytearray()
            while True:
                c = s.recv(1)
                if not c:
                    raise RuntimeError("eof")
                if c == b"$":
                    break
            while True:
                c = s.recv(1)
                if not c:
                    raise RuntimeError("eof")
                if c == b"#":
                    break
                buf += c
            s.recv(2)
            s.sendall(b"+")
            return bytes(buf)

        s.settimeout(1)
        try:
            while True:
                print("  [init]", recv()[:24], flush=True)
        except Exception:
            pass
        s.settimeout(4)

        for addr, n in TESTS:
            payload = b"m%x,%x" % (addr, n)
            t0 = time.time()
            try:
                s.sendall(b"$" + payload + b"#%02X" % (sum(payload) & 0xFF))
                pkt = recv()
                dt = time.time() - t0
                if pkt.startswith(b"E"):
                    print(f"0x{addr:08X},{n:#06x}: ERR {pkt[:10]} ({dt:.2f}s)",
                          flush=True)
                else:
                    print(f"0x{addr:08X},{n:#06x}: OK {len(pkt) // 2}B ({dt:.2f}s) "
                          f"{pkt[:24].decode(errors='replace')}", flush=True)
            except Exception as e:
                print(f"0x{addr:08X},{n:#06x}: EXC {type(e).__name__} "
                      f"({time.time() - t0:.2f}s)", flush=True)
                break
        s.close()
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
