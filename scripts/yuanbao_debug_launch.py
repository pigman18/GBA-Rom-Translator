#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Relaunch the Yuanbao desktop app with the WebView2 DevTools port open.

Yuanbao renders its UI in an Edge WebView2 control. WebView2 ignores host
command-line switches, so the only supported way to pass Chromium flags is the
WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS environment variable, which must be set
before the host process spawns the browser process.

    python yuanbao_debug_launch.py [--port 9222] [--no-kill]

Exits 0 once the DevTools HTTP endpoint answers, 1 on timeout.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request

EXE = r"C:\Program Files\Tencent\Yuanbao\yuanbao.exe"
PROC = "yuanbao.exe"
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def kill_running() -> None:
    print(f"[i] stopping {PROC} ...")
    r = subprocess.run(
        ["taskkill", "/F", "/IM", PROC, "/T"],
        capture_output=True,
    )
    # taskkill prints localized (GBK) text on Chinese Windows; never trust utf-8 here.
    out = (r.stdout or b"").decode("gbk", errors="replace").strip()
    err = (r.stderr or b"").decode("gbk", errors="replace").strip()
    print("   ", (out or err).replace("\n", " | "))
    time.sleep(2)


def wait_port(port: int, timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    waited = 0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                info = r.read().decode("utf-8", "replace")
            print(f"[v] DevTools is up on port {port} after {waited}s")
            print(f"    {info[:200]}")
            return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
        waited += 2
        if waited % 10 == 0:
            print(f"    waiting... {waited}s")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--no-kill", action="store_true", help="do not stop the running instance")
    ap.add_argument("--exe", default=EXE)
    args = ap.parse_args()

    if not os.path.isfile(args.exe):
        print(f"[x] not found: {args.exe}")
        return 1

    if not args.no_kill:
        kill_running()

    env = dict(os.environ)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={args.port}"

    print(f"[i] launching {args.exe}")
    print(f"    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS={env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']}")
    subprocess.Popen(
        [args.exe],
        env=env,
        cwd=os.path.dirname(args.exe),
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

    if wait_port(args.port):
        print("[v] done. Next: python yuanbao_cdp.py list")
        return 0

    print(f"[x] DevTools never appeared on port {args.port}")
    print("    The WebView2 runtime may refuse the switch (some hosts lock it down),")
    print("    or the app may not have created a browser process yet.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
