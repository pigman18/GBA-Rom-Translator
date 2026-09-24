# -*- coding: utf-8 -*-
"""run_buildbat.py —— 在 shell 编码不可靠时忠实执行仓库根 build.bat。

它**不手抄任何参数**：直接读 build.bat 的 meowth 命令行，按行原样拆 argv，
用当前解释器 `-m meowth` 重放。模块清单因此仍以 build.bat 为唯一权威来源。

⚠ build.bat 是 **GBK/CP936** 编码的批处理文件（含中文模块名），必须按 gbk 读，
  否则模块名会变乱码（实测：按 utf-8 读 → 一屏 `????`，meowth 收不到模块）。

用法：<python> .tmp/an/run_buildbat.py [附加参数 ...]
"""
from __future__ import annotations
import os
import shlex
import subprocess
import sys

ROOT = r"C:\code\GBA-Rom-Translator"
BAT = os.path.join(ROOT, "build.bat")

raw = open(BAT, "r", encoding="gbk", errors="replace").read()
line = [l.strip() for l in raw.splitlines() if "meowth" in l and " full " in l]
if len(line) != 1:
    print("!! build.bat 里找到 %d 条 meowth full 命令行" % len(line))
    raise SystemExit(2)

toks = shlex.split(line[0], posix=False)
# toks[0] = build.bat 里硬编码的解释器路径 → 换成当前解释器
toks[0] = sys.executable

argv = toks + sys.argv[1:]
env = dict(os.environ)
env["PYTHONPATH"] = os.path.join(ROOT, "src")

print("cwd  =", ROOT)
print("argv =")
for a in argv:
    print("   ", a)
print("-" * 70, flush=True)

log = open(os.path.join(ROOT, "pack_log_v1f4.txt"), "w",
           encoding="utf-8", errors="replace")
p = subprocess.Popen(argv, cwd=ROOT, env=env,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, encoding="utf-8", errors="replace")
for ln in p.stdout:
    sys.stdout.write(ln)
    log.write(ln)
log.close()
print("-" * 70)
print("rc =", p.wait())
