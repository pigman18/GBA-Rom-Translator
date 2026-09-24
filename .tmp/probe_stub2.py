#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GDB stub 通路探针 v2：可选 Qt/SDL 版、可选 savestate，带 netstat 诊断。

用法: probe_stub2.py [qt|sdl] [savestate|-]
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
BASE = ROOT / "tools" / "mGBA-0.10.5-win32"
EXES = {"sdl": BASE / "mgba-sdl.exe", "qt": BASE / "mGBA.exe"}
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
PORT = 2345


def ports_of(pid: int) -> list[str]:
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             errors="replace", timeout=15).stdout
    except Exception as e:
        return [f"netstat err {e}"]
    hits = [ln.strip() for ln in out.splitlines() if "LISTEN" in ln.upper()]
    return [ln for ln in hits if str(pid) in ln.split()[-1:]] or [
        f"(该 pid {pid} 无监听) 总监听数={len(hits)}"]


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "sdl"
    state = sys.argv[2] if len(sys.argv) > 2 else "-"
    exe = EXES[which]
    log = ROOT / ".tmp" / f"probe_{which}.out"

    args = [str(exe), "-g", "-1"]
    if state != "-":
        args += ["-t", state]
    args.append(str(ROM))
    print("argv:", args, flush=True)

    fo = open(log, "wb")
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
            if i == 15:
                print("netstat:", ports_of(proc.pid), flush=True)
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

    print("=== 模拟器输出 ===", flush=True)
    try:
        txt = log.read_text(encoding="utf-8", errors="replace")
        print(txt[:1500] if txt else "(空)", flush=True)
    except OSError as e:
        print("读日志失败:", e, flush=True)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
