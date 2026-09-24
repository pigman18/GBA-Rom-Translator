import subprocess, os, sys

PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
os.chdir(r"C:/code/GBA-Rom-Translator")

# 进设置页：START 打开菜单 -> 6 次 DOWN 到「设置」-> A 进入
SCHED = ("A:240-280,A:330-370,A:420-460,A:510-550,A:600-640,A:690-730,"
         "A:780-820,A:870-910,A:960-1000,A:1050-1090,A:1140-1180,A:1230-1270,"
         "START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,DOWN:2000-2040,"
         "DOWN:2150-2190,DOWN:2300-2340,DOWN:2450-2490,A:2600-2640,A:2750-2790")
TAG = sys.argv[1] if len(sys.argv) > 1 else "orgOpt"
FRAMES = "3100"
ROM = "roms/origin/POKEMON_RUBY_AXVJ00.gba"

env = dict(os.environ)
env["PATH"] = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\usr\bin;" + env.get("PATH", "")

r = subprocess.run([PY, "scripts/mgba_drive.py", "--schedule", SCHED, "--frames", FRAMES,
                    "--tag", TAG, "--rom", ROM, "--dump"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                   timeout=900)
print("rc =", r.returncode)
for ln in (r.stdout or "").splitlines():
    if any(k in ln for k in ("IO ", "dump", "final shot", "ERROR", "ABORT", "shot")):
        print(ln)
