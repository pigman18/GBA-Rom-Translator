#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线打包（--seed-only，不调 LLM）—— 与根 build.bat 的模块清单/参数**逐字一致**，
只多一个 --seed-only。

为什么用 Python 驱动而不是直接跑 build.bat：
  根 build.bat 含中文模块名，Git Bash / PowerShell 5.1 都会按代码页转换非 ASCII 参数
  （AGENTS.md 已警告）。Python 的 subprocess 走 CreateProcessW（Unicode），零转码风险。

用法: python scripts/pack_seed.py [--with-llm]
      （不给 --with-llm 时 = --seed-only；给了就与根 build.bat 完全一致）
"""
import os
import subprocess
import sys

ROOT = r"C:\code\GBA-Rom-Translator"
PY = r"C:\Python314\python.exe"
ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
OUT = r"C:\code\GBA-Rom-Translator\roms\outputs"

MODULES = ",".join([
    "属性名", "属性名-华丽大赛", "性格名", "特性名", "宝可梦名", "招式名",
    "招式名-华丽大赛", "训练家名", "训练家个人名", "地点名", "秘密基地装饰名",
    "道具名", "树果名", "道具说明", "招式说明", "招式说明-华丽大赛", "特性说明",
    "图鉴分类名", "图鉴说明", "UI界面", "剧情", "补漏剧情",
])

API_KEY = ("sk-ws-H.PMDLEPE.5Csa.MEUCIQCJxiC5q6nB03cej_ANbo_Ez9t2XNO_WeU_xenY4zqcugIg"
           "TgSiF_eQTqoaI7q527WlypRIExGI3_gwqX_5_XjBpDE")

args = [
    PY, "-m", "meowth", "full", ROM,
    "-o", OUT,
    "--work-dir", "work",
    "--source", "ja",
    "--target", "zh-Hans",
    "--modules", MODULES,
    "--provider", "qwen",
    "--model", "qwen3.5-omni-flash",
    "--api-key=" + API_KEY,
]
if "--with-llm" not in sys.argv:
    args.append("--seed-only")

env = dict(os.environ)
env["PYTHONPATH"] = os.path.join(ROOT, "src")
env["PYTHONIOENCODING"] = "utf-8"

print("cwd  =", ROOT)
print("argv =", args[:6], "...  modules=%d 个" % len(MODULES.split(",")),
      "seed_only=%s" % ("--seed-only" in args))
sys.stdout.flush()

rc = subprocess.run(args, cwd=ROOT, env=env).returncode
print("meowth full rc =", rc)
sys.exit(rc)
