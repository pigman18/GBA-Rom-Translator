#!/usr/bin/env python3
"""最小验证：脚本全程持有 GUI mGBA -g，立刻连 GDB，验证 stub 可用。

不 detached、不后台、脚本不退出 —— 排除「父进程死带走子进程」这条线。
"""
import os
import re
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
OUTLOG = os.path.join(ROOT, ".tmp", "mgba_launch.out")


def main() -> int:
    fo = open(OUTLOG, "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"[t] mGBA pid={p.pid}", flush=True)

    # 轮询：等 stub 端口出现（不主动连接，只 netstat 看）
    found = False
    for i in range(20):
        time.sleep(0.7)
        if p.poll() is not None:
            print(f"[t] mGBA 已退出 rc={p.returncode}（{i}）", flush=True)
            break
        ns = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                            errors="replace").stdout
        if ":2345" in ns and "LISTENING" in ns:
            print(f"[t] 端口 LISTENING @ {i*0.7:.1f}s", flush=True)
            found = True
            break
    if not found and p.poll() is None:
        print("[t] 8+ 秒内未监听 2345，进程仍在", flush=True)

    # 连接
    try:
        g = GdbClient("127.0.0.1", 2345, timeout=8.0)
        g.connect()
        print("[t] GDB 连接 OK", flush=True)
        regs = g.read_regs()
        print("[t] pc=0x%08X sp=0x%08X lr=0x%08X" % (
            regs.get("r15", 0), regs.get("r13", 0), regs.get("r14", 0)), flush=True)
        print("[t] M 写:", repr(g.cmd("M4000130,2,ff03")), flush=True)
        print("[t] 读回 KEYINPUT:", g.read_mem(0x04000130, 2).hex(), flush=True)
        t0 = time.time()
        try:
            r = g.cont(timeout=1.0)
            print(f"[t] cont 返回({time.time()-t0:.1f}s): {r[:100]!r}", flush=True)
        except Exception as e:
            print(f"[t] cont 异常({time.time()-t0:.1f}s): {type(e).__name__} {e}", flush=True)
        regs = g.read_regs()
        print("[t] cont后 pc=0x%08X" % (regs.get("r15", 0),), flush=True)
        g.close()
    except Exception as e:
        print("[t] GDB 失败:", type(e).__name__, e, flush=True)

    # 留 3 秒观察进程是否稳定
    time.sleep(3)
    print(f"[t] 最终 poll={p.poll()}", flush=True)
    if p.poll() is None:
        print(f"[t] 进程存活，pid={p.pid}（脚本退出后会随之结束，仅用于验证）", flush=True)
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    fo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
