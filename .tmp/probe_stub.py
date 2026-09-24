#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GDB stub 通路探针：单进程内启动 mgba-sdl -> 轮询连接 -> dump -> 退出。

目的：把「启动失败 / 端口未开 / 协议错」三种情况分开，不再靠猜。
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
EXE = ROOT / "tools" / "mGBA-0.10.5-win32" / "mgba-sdl.exe"
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
LOG = ROOT / ".tmp" / "probe_stub.out"

PORT = 2345


def main() -> int:
    args = [str(EXE), "-g", "-1"]
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        args += ["-t", sys.argv[1]]
    args.append(str(ROM))
    print("argv:", args, flush=True)

    fo = open(LOG, "wb")
    proc = subprocess.Popen(args, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                            stdout=fo, stderr=fo, close_fds=True)
    print("pid:", proc.pid, flush=True)

    ok = False
    s = None
    for i in range(40):
        if proc.poll() is not None:
            print(f"进程提前退出 rc={proc.returncode} @ attempt {i}", flush=True)
            break
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=1.0)
            print(f"连上 stub @ attempt {i} ({i * 0.5:.1f}s)", flush=True)
            ok = True
            break
        except OSError:
            time.sleep(0.5)

    if ok and s is not None:
        try:
            s.settimeout(5.0)

            def exc(payload: bytes) -> bytes:
                csum = sum(payload) & 0xFF
                s.sendall(b"$" + payload + b"#%02X" % csum)
                buf = bytearray()
                while True:
                    c = s.recv(1)
                    if not c:
                        raise RuntimeError("eof")
                    if c == b"$":
                        break
                while True:
                    c = s.recv(1)
                    if c == b"#":
                        break
                    buf += c
                s.recv(2)
                s.sendall(b"+")
                return bytes(buf)

            print("stop-reply:", exc(b"?")[:80], flush=True)
            r = exc(b"g")
            print("regs len:", len(r), "pc=", r[15 * 8:15 * 8 + 8], flush=True)
            print("DISPCNT:", exc(b"m4000000,4"), flush=True)
        except Exception as e:
            print("协议交互失败:", type(e).__name__, e, flush=True)
            ok = False
        finally:
            try:
                s.close()
            except OSError:
                pass

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    fo.close()

    print("=== mgba-sdl 输出 ===", flush=True)
    try:
        txt = LOG.read_text(encoding="utf-8", errors="replace")
        print(txt[:2000] if txt else "(空)", flush=True)
    except OSError as e:
        print("读日志失败:", e, flush=True)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
