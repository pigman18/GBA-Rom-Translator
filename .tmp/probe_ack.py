#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测 mGBA stub 的 ACK 行为：连读 4 次同一地址，比较「回 +」与「不回 +」。

用法: probe_ack.py <ack|noack> [count]
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
EXE = ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
PORT = 2345


def main():
    ack = (sys.argv[1] if len(sys.argv) > 1 else "ack") == "ack"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    log = ROOT / ".tmp" / "probe_ack.out"
    fo = open(log, "wb")
    proc = subprocess.Popen([str(EXE), "-g", "-1", str(ROM)], cwd=str(ROOT),
                            stdin=subprocess.DEVNULL, stdout=fo, stderr=fo,
                            close_fds=True)
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
        s.settimeout(3)
        print(f"--- ack={ack} ---", flush=True)

        def raw_recv():
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
            return bytes(buf)

        # drain 初始包
        s.settimeout(1)
        try:
            while True:
                print("  [init]", raw_recv()[:30], flush=True)
        except Exception:
            pass
        s.settimeout(3)

        for i in range(count):
            payload = b"m4000000,4"
            t0 = time.time()
            s.sendall(b"$" + payload + b"#%02X" % (sum(payload) & 0xFF))
            try:
                pkt = raw_recv()
                print(f"  read#{i}: OK {pkt[:20]} ({time.time() - t0:.2f}s)",
                      flush=True)
                if ack:
                    s.sendall(b"+")
            except Exception as e:
                print(f"  read#{i}: {type(e).__name__} ({time.time() - t0:.2f}s)",
                      flush=True)
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
