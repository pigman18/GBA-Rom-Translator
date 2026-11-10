#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dump command lines for a given process name via CIM, with visible errors.

Used to confirm whether Yuanbao's WebView2 browser process picked up
--remote-debugging-port from WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS.
"""

from __future__ import annotations

import subprocess
import sys
import time

PS = """
$ErrorActionPreference = 'Stop'
$procs = Get-CimInstance Win32_Process -Filter "Name='{name}'"
foreach ($p in $procs) {{
  $cl = [string]$p.CommandLine
  if ($cl -match '{pattern}') {{
    Write-Output ('PID ' + $p.ProcessId + ' :: ' + ($cl -replace '\\s+', ' '))
  }}
}}
Write-Output ('TOTAL_MATCHED_DONE')
"""


def run(name: str, pattern: str) -> None:
    cmd = PS.format(name=name, pattern=pattern)
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("[x] powershell timed out after 120s")
        return

    print(f"--- filter Name='{name}' pattern='{pattern}' ---")
    print("rc =", r.returncode)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    print(out if out else "(no stdout)")
    if err:
        print("STDERR:", err[:800])
    print()


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "msedgewebview2.exe"
    pattern = sys.argv[2] if len(sys.argv) > 2 else "."
    t0 = time.time()
    run(name, pattern)
    print(f"[i] took {time.time() - t0:.1f}s")
