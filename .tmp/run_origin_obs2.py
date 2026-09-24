"""观测用 2：原盘副本 + 原盘存档 + 池字预置，驱动到设置页。
只读原盘/存档，写出到 .tmp/，不触碰 roms/outputs 与补丁产物。
"""
import shutil, struct, os, subprocess, sys

ROOT = r"C:/code/GBA-Rom-Translator"
os.chdir(ROOT)
PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

SRC = "roms/origin/POKEMON_RUBY_AXVJ00.gba"
SAV = "roms/origin/POKEMON_RUBY_AXVJ00.sav"
DST = os.path.join(ROOT, ".tmp", "obs_origin.gba")
DSV = os.path.join(ROOT, ".tmp", "obs_origin.sav")
POOL_OFF = 0x08000468 - 0x08000000

b = bytearray(open(SRC, "rb").read())
old = struct.unpack_from("<I", b, POOL_OFF)[0]
print("pool word @0x08000468 = 0x%08X -> 0x08900000" % old)
struct.pack_into("<I", b, POOL_OFF, 0x08900000)
open(DST, "wb").write(bytes(b))
shutil.copyfile(SAV, DSV)
print("rom:", DST, os.path.getsize(DST), " sav:", DSV, os.path.getsize(DSV))

# 标题 -> 继续 -> 读档 -> 游戏内 -> START 菜单 -> 6xDOWN -> A 进「设置」
SCHED = ("A:180-220,START:300-340,A:430-470,"
         "A:600-640,START:700-740,A:830-870,"
         "START:1200-1240,"
         "DOWN:1400-1440,DOWN:1520-1560,DOWN:1640-1680,"
         "DOWN:1760-1800,DOWN:1880-1920,DOWN:2000-2040,"
         "A:2200-2240,A:2350-2390")
TAG = sys.argv[1] if len(sys.argv) > 1 else "org2"
FRAMES = "2700"

env = dict(os.environ)
env["PATH"] = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\usr\bin;" + env.get("PATH", "")

r = subprocess.run([PY, "scripts/mgba_drive.py", "--schedule", SCHED, "--frames", FRAMES,
                    "--tag", TAG, "--rom", DST, "--no-redirect",
                    "--shot-times", "8,14,20,26,32,38,45",
                    "--dump"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                   timeout=900)
print("rc =", r.returncode)
for ln in (r.stdout or "").splitlines():
    if any(k in ln for k in ("IO ", "dump", "final shot", "ERROR", "ABORT", "shot")):
        print(ln)
