"""观测用：原盘副本 + 池字预置，用于按键注入。
只读原盘 bytes，写出 .tmp/obs_origin.gba（不触碰 roms/ 与补丁产物）。
"""
import shutil, struct, os, subprocess, sys

ROOT = r"C:/code/GBA-Rom-Translator"
os.chdir(ROOT)
PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

SRC = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
DST = os.path.join(ROOT, ".tmp", "obs_origin.gba")
POOL_OFF = 0x08000468 - 0x08000000   # = 0x468

b = bytearray(open(SRC, "rb").read())
print("origin size =", len(b))
old = struct.unpack_from("<I", b, POOL_OFF)[0]
print("pool word @0x08000468 = 0x%08X" % old)
struct.pack_into("<I", b, POOL_OFF, 0x08900000)
open(DST, "wb").write(bytes(b))
print("wrote", DST, "pool -> 0x08900000")

SCHED = ("A:240-280,A:330-370,A:420-460,A:510-550,A:600-640,A:690-730,"
         "A:780-820,A:870-910,A:960-1000,A:1050-1090,A:1140-1180,A:1230-1270,"
         "START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,DOWN:2000-2040,"
         "DOWN:2150-2190,DOWN:2300-2340,DOWN:2450-2490,A:2600-2640,A:2750-2790")
TAG = sys.argv[1] if len(sys.argv) > 1 else "orgObs"
FRAMES = "3100"

env = dict(os.environ)
env["PATH"] = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\usr\bin;" + env.get("PATH", "")

r = subprocess.run([PY, "scripts/mgba_drive.py", "--schedule", SCHED, "--frames", FRAMES,
                    "--tag", TAG, "--rom", DST, "--no-redirect", "--dump"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                   timeout=900)
print("rc =", r.returncode)
for ln in (r.stdout or "").splitlines():
    if any(k in ln for k in ("IO ", "dump", "final shot", "ERROR", "ABORT", "shot", "keys")):
        print(ln)
