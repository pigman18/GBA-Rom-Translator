# -*- coding: utf-8 -*-
"""冷启动（不用 savestate）+ .sav，逐页驱动并 dump，用于本轮 5 条反馈的验收。
用法: python .tmp/verify_pages.py [tag ...]
"""
import os
import subprocess
import sys

PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
os.chdir(r"C:/code/GBA-Rom-Translator")
ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"

AS12 = ",".join("A:%d-%d" % (240 + i * 90, 280 + i * 90) for i in range(12))
BOOT = AS12
MENU = BOOT + ",START:1500-1540"

PAGES = {
    # tag:      (schedule, frames)
    "v_party": (MENU + ",DOWN:1700-1740,A:1900-1940", "2300"),
    "v_sum":   (MENU + ",DOWN:1700-1740,A:1900-1940,A:2050-2090,A:2200-2240", "2600"),
    "v_bag":   (MENU + ",DOWN:1700-1740,DOWN:1850-1890,A:2000-2040", "2500"),
    "v_nav":   (MENU + ",DOWN:1700-1740,DOWN:1850-1890,DOWN:2000-2040,A:2150-2190",
                "2700"),
    "v_opt":   (BOOT + ",START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,"
                       "DOWN:2000-2040,DOWN:2150-2190,DOWN:2300-2340,"
                       "DOWN:2450-2490,A:2600-2640,A:2750-2790", "3100"),
}

want = sys.argv[1:] or list(PAGES)
env = dict(os.environ)
env["PATH"] = (r"C:\Users\Administrator\.workbuddy\binaries\PortableGit"
               r"\versions\1.2.0\usr\bin;" + env.get("PATH", ""))

for tag in want:
    sched, frames = PAGES[tag]
    r = subprocess.run([PY, "scripts/mgba_drive.py", "--rom", ROM,
                        "--schedule", sched, "--frames", frames,
                        "--tag", tag, "--dump"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=900)
    print("==", tag, "rc", r.returncode, flush=True)
    for ln in (r.stdout or "").splitlines():
        if "final shot" in ln or "ERROR" in ln or "ABORT" in ln:
            print("   ", ln.strip(), flush=True)
