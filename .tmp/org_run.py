# -*- coding: utf-8 -*-
"""org_run.py — 用**原盘**冷启动跑同样页面并 dump（做 A/B 对照）。"""
import os, subprocess, sys
PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
ROOT = r"C:/code/GBA-Rom-Translator"
ROM = r"C://code//GBA-Rom-Translator//roms//origin//POKEMON_RUBY_AXVJ00.gba"
AS12 = ",".join("A:%d-%d" % (240 + i * 90, 280 + i * 90) for i in range(12))
MENU = AS12 + ",START:1500-1540"
PAGES = {
    "o_party": (MENU + ",DOWN:1700-1740,A:1900-1940", "2300"),
    "o_sum":   (MENU + ",DOWN:1700-1740,A:1900-1940", "2300"),
    "o_sum2":  (MENU + ",DOWN:1700-1740,A:1900-1940,"
                       "RIGHT:2050-2090,RIGHT:2200-2240,RIGHT:2350-2390", "2800"),
    "o_bag":   (MENU + ",DOWN:1700-1740,DOWN:1850-1890,A:2000-2040", "2500"),
    # 概况页（LV/HP/能力）—— 对照我方 t_info
    "o_info":  (MENU + ",DOWN:1700-1740,A:1900-1940,A:2050-2090,A:2250-2290", "2700"),
    # 对战技能页（PP）—— 对照我方 t_moves
    "o_moves": (MENU + ",DOWN:1700-1740,A:1900-1940,A:2050-2090,A:2250-2290,"
                       "RIGHT:2500-2540,RIGHT:2700-2740,RIGHT:2900-2940", "3300"),
}
def main(want):
    os.chdir(ROOT)
    env = dict(os.environ)
    env["PATH"] = (r"C://Users//Administrator//.workbuddy//binaries//PortableGit"
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
if __name__ == "__main__":
    main(sys.argv[1:] or list(PAGES))

