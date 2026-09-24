#!/usr/bin/env python3
"""真正脱离父进程地起 mgba-sdl -g（避免随 shell/父进程退出而死）。

坑位记录（2026-09-20）：
  - bash `&` 后台作业随 shell 退出被 SIGKILL
  - DETACHED_PROCESS 单独用仍被 job object 牵连 ⇒ 必须 CREATE_BREAKAWAY_FROM_JOB
  - 不要探测 2345 端口（stub 只接一个客户端，探测会占槽）
"""
import os
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
WORKDIR = os.path.join(ROOT, ".tmp", "mgba-b1")
EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mgba-sdl.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")
OUT = os.path.join(WORKDIR, "sdl.out")

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

FLAGS = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB


def main() -> int:
    os.makedirs(WORKDIR, exist_ok=True)
    fo = open(OUT, "wb")
    args = [EXE, "-g", "-l", "0", "-1",
            "-C", "logToFile=0", "-C", "logToStdout=0",
            ROM]
    p = subprocess.Popen(args, cwd=WORKDIR, creationflags=FLAGS,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo,
                         close_fds=True)
    print(f"pid={p.pid}", flush=True)
    # 父进程退出前不 join —— 靠 BREAKAWAY 脱离
    time.sleep(8)
    # 报告状态
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mgba-sdl.exe",
                              "/FO", "CSV"], capture_output=True, text=True,
                             errors="replace")
        print(out.stdout.strip(), flush=True)
    except Exception as e:
        print("tasklist err", e, flush=True)
    try:
        ns = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                            errors="replace")
        lines = [l for l in ns.stdout.splitlines() if "2345" in l]
        print("PORT2345:", lines or "(none)", flush=True)
    except Exception as e:
        print("netstat err", e, flush=True)
    return p.pid


if __name__ == "__main__":
    sys.exit(main())
