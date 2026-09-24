import subprocess, os, sys

PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
os.chdir(r"C:/code/GBA-Rom-Translator")

AS = ",".join("A:%d-%d" % (240 + i * 90, 280 + i * 90) for i in range(12))

VARIANTS = {
    # 停在 PokéNav 主菜单（进入 PokéNav 的第 1 屏，含 11x11 的「查看丰缘地区的地图」）
    "navm": (AS + ",START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,"
                  "DOWN:2000-2040,A:2250-2290", "2400"),
    # 只按 START 看主菜单（tm3 路径）
    "start": (AS + ",START:1500-1540", "1750"),
    # 主菜单 -> 保存（检查 tm3 下更多行）
    "start2": (AS + ",START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,"
                    "DOWN:2000-2040,DOWN:2150-2190,DOWN:2300-2340", "2500"),
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
