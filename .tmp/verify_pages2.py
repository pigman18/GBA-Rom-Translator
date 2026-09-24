# -*- coding: utf-8 -*-
import os, subprocess, sys
PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
os.chdir(r"C:/code/GBA-Rom-Translator")
ROM = r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
AS12 = ",".join("A:%d-%d" % (240 + i * 90, 280 + i * 90) for i in range(12))
MENU = AS12 + ",START:1500-1540"
PAGES = {
    # 背包：进背包后再往下列 4 格（对齐用户截图的位置）
    "x_bag2": (MENU + ",DOWN:1700-1740,DOWN:1850-1890,A:2000-2040,"
                      "DOWN:2200-2240,DOWN:2300-2340,DOWN:2400-2440,"
                      "DOWN:2500-2540,DOWN:2600-2640", "3200"),
    # 详情页：进详情后按 RIGHT 切分页到「对战技能」
    "x_sum2": (MENU + ",DOWN:1700-1740,A:1900-1940,"
                      "RIGHT:2050-2090,RIGHT:2200-2240,RIGHT:2350-2390", "2800"),
}
want = sys.argv[1:] or list(PAGES)
env = dict(os.environ)
env["PATH"] = (r"C:/Users/Administrator/.workbuddy/binaries/PortableGit"
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
