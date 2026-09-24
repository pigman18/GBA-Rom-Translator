import subprocess, os

PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
os.chdir(r"C:/code/GBA-Rom-Translator")

SCHED = ("A:240-280,A:330-370,A:420-460,A:510-550,A:600-640,A:690-730,"
         "A:780-820,A:870-910,A:960-1000,A:1050-1090,A:1140-1180,A:1230-1270,"
         "START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,DOWN:2000-2040,"
         "DOWN:2150-2190,DOWN:2300-2340,DOWN:2450-2490")

env = dict(os.environ)
env["PATH"] = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\usr\bin;" + env.get("PATH", "")

r = subprocess.run([PY, "scripts/mgba_drive.py", "--schedule", SCHED, "--frames", "2700",
                    "--tag", "dbg1", "--dump"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                   timeout=600)
print("rc =", r.returncode)
print((r.stdout or "")[-3000:])
print("--- stderr ---")
print((r.stderr or "")[-1000:])
