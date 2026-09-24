import subprocess, time, socket, sys, os

PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
GDB = r"C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
os.chdir(r"C:/code/GBA-Rom-Translator")

SCHED = ("A:240-280,A:330-370,A:420-460,A:510-550,A:600-640,A:690-730,"
         "A:780-820,A:870-910,A:960-1000,A:1050-1090,A:1140-1180,A:1230-1270,"
         "START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,DOWN:2000-2040,"
         "DOWN:2150-2190,DOWN:2300-2340,DOWN:2450-2490")
FRAMES = "2700"
GDBFILE = sys.argv[1] if len(sys.argv) > 1 else ".tmp/sample_win.gdb"
OUT = sys.argv[2] if len(sys.argv) > 2 else ".tmp/win_out.txt"
WAIT = int(sys.argv[3]) if len(sys.argv) > 3 else 100

env = dict(os.environ)
env["PATH"] = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\usr\bin;" + env.get("PATH", "")

do_drive = os.environ.get("SKIP_DRIVE") != "1"
if do_drive:
    print("[1] driving ROM ...", flush=True)
    r = subprocess.run([PY, "scripts/mgba_drive.py", "--schedule", SCHED, "--frames", FRAMES,
                        "--tag", "win1", "--keep-alive", "--no-capture"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    print("[1] drive rc =", r.returncode)
    print("[1] tail:", (r.stdout or "")[-300:])

print("[2] waiting for gdb stub port 2345 ...", flush=True)
ok = False
for i in range(30):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", 2345))
        ok = True
        s.close()
        break
    except Exception:
        time.sleep(0.5)
print("[2] port open =", ok, "after", i, "tries")

print("[3] gdb sampling (max %ds) ..." % WAIT, flush=True)
with open(OUT, "w", encoding="utf-8", errors="replace") as f:
    p = subprocess.Popen([GDB, "-nx", "-batch", "-x", GDBFILE],
                         stdout=f, stderr=subprocess.STDOUT, env=env)
    try:
        p.wait(timeout=WAIT)
        print("[3] gdb exited rc =", p.returncode)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
        print("[3] gdb TIMEOUT -> killed")

txt = open(OUT, encoding="utf-8", errors="replace").read()
print("[3] out chars =", len(txt))
print("=" * 70)
print(txt[:7000])
