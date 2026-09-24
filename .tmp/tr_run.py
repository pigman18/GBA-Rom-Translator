# -*- coding: utf-8 -*-
"""tr_run.py — 用带追踪的 ROM 冷启动跑若干页面并 dump（含 EWRAM 采样块）。

用法:  python .tmp/tr_run.py [tag ...]     默认全跑
"""
import os
import subprocess
import sys

PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
ROOT = r"C:/code/GBA-Rom-Translator"
ROM = os.environ.get("CHS_ROM", r"C:\code\GBA-Rom-Translator\roms\outputs\_t2.gba")

AS12 = ",".join("A:%d-%d" % (240 + i * 90, 280 + i * 90) for i in range(12))
MENU = AS12 + ",START:1500-1540"

PAGES = {
    # 标题画面（继续游戏 / 新游戏 / 设置 + 存档摘要）
    "t_title": (AS12, "1400"),
    # 主菜单（继续游戏 / 新游戏 / 设置）—— 用户截图 7（UI 撞）
    "t_menu": (MENU, "1700"),
    # 背包（光标在 学习装置）—— 用户截图 1
    "t_bag": (MENU + ",DOWN:1700-1740,DOWN:1850-1890,A:2000-2040", "2500"),
    # 背包（光标下移 2 格）—— 用户截图 2
    "t_bag2": (MENU + ",DOWN:1700-1740,DOWN:1850-1890,A:2000-2040,"
                      "DOWN:2200-2240,DOWN:2300-2340", "2700"),
    # 队伍页 —— 用户截图 3（请选择）
    "t_party": (MENU + ",DOWN:1700-1740,A:1900-1940", "2300"),
    # 详情页-信息 —— 用户截图 4（Lv）
    "t_sum": (MENU + ",DOWN:1700-1740,A:1900-1940,A:2050-2090", "2500"),
    # 详情页-对战技能 —— 用户截图 5/6（PP / 图标）
    "t_sum2": (MENU + ",DOWN:1700-1740,A:1900-1940,A:2050-2090,"
                       "RIGHT:2250-2290,RIGHT:2400-2440,RIGHT:2550-2590", "2900"),
    # 详情页-概况（Lv / HP / 能力）—— 用户反馈「LV 撞了显示不出来」
    "t_info": (MENU + ",DOWN:1700-1740,A:1900-1940,A:2050-2090,A:2250-2290", "2700"),
    # 详情页-对战技能（PP）—— 从概况页 RIGHT 翻到技能页
    "t_moves": (MENU + ",DOWN:1700-1740,A:1900-1940,A:2050-2090,A:2250-2290,"
                        "RIGHT:2500-2540,RIGHT:2700-2740,RIGHT:2900-2940", "3300"),
}


def main(want):
    os.chdir(ROOT)
    env = dict(os.environ)
    env["PATH"] = (r"C:\Users\Administrator\.workbuddy\binaries\PortableGit"
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
            if ("final shot" in ln or "ERROR" in ln or "ABORT" in ln
                    or "[io]" in ln or "dump " in ln):
                print("   ", ln.strip(), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(PAGES))
