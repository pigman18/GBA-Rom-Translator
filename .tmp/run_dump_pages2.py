import subprocess, os, sys

PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
os.chdir(r"C:/code/GBA-Rom-Translator")

AS = ",".join("A:%d-%d" % (240 + i * 90, 280 + i * 90) for i in range(12))
MENU = AS + ",START:1500-1540"

VARIANTS = {
    "party": (MENU + ",DOWN:1700-1740,A:1900-1940", "2300"),
    "bag":   (MENU + ",DOWN:1700-1740,DOWN:1850-1890,A:2050-2090", "2450"),
    "sum":   (MENU + ",DOWN:1700-1740,A:1900-1940,A:2100-2140,"
                    "RIGHT:2400-2440", "2750"),
    "sum1":  (MENU + ",DOWN:1700-1740,A:1900-1940,A:2100-2140", "2600"),
}

tag = sys.argv[1]
sched, frames = VARIANTS[tag]

env = dict(os.environ)
env["PATH"] = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\usr\bin;" + env.get("PATH", "")

r = subprocess.run([PY, "scripts/mgba_drive.py", "--schedule", sched, "--frames", frames,
                    "--tag", tag, "--dump"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                   timeout=900)
print("rc =", r.returncode)
for ln in (r.stdout or "").splitlines():
    if any(k in ln for k in ("IO ", "dump", "final shot", "ERROR", "ABORT", "shot")):
        print(ln)
