# -*- coding: utf-8 -*-
"""genpool.py -- 按 freemap 的空档 + 人口归属，直接生成 C 段表。

归属规则（人工裁定，见 poolchk 的实测依据）：
  · 人口 0 = cb1 窗口（td=0x06004000，实测＝左面板/队名）
      要 [0x06007000,0x06007800) + [0x0600B640,0x0600C000)
  · 人口 1 = cb2 窗口（td=0x06008000，实测＝概况页右栏/技能列表/菜单）
      要 [0x06008000,0x0600B640) 的碎片 + [0x0600C1C0,0x0600CB60) + [0x0600CC80,0x0600E000)
  · 人口 2 = cb0 窗口（td=0x06000000，未实测）要 [0x06001800,0x06002000)+[0x06002800,0x06003000)

用法: python .tmp/genpool.py
"""
import re
import subprocess
import sys
from pathlib import Path

BLK = {0: 0x06004000, 1: 0x06008000, 2: 0x06000000}
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")


def free_runs():
    out = subprocess.run([sys.executable, str(T / "freemap.py")],
                         capture_output=True, text=True, encoding="utf-8")
    runs = []
    for ln in out.stdout.splitlines():
        m = re.search(r"空档 \[([0-9A-F]+),([0-9A-F]+)\)\s+(\d+) 砖", ln)
        if m:
            runs.append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3))))
    return runs


# 归属：绝对地址区间
ASSIGN = {
    0: [(0x06007000, 0x06007800), (0x0600B640, 0x0600C000)],
    1: [(0x06008000, 0x0600B640), (0x0600C1C0, 0x0600CB60), (0x0600CC80, 0x0600E000)],
    2: [(0x06001800, 0x06002000), (0x06002800, 0x06003000)],
}


def main():
    runs = free_runs()
    for dom in (0, 1, 2):
        base = BLK[dom]
        segs = []
        for lo, hi in ASSIGN[dom]:
            for a, b, n in runs:
                s, e = max(a, lo), min(b, hi)
                if e - s >= 32 * 4:            # stride=2：1 槽 = 2 tile
                    k = (e - s) // 64
                    segs.append(((s - base) // 32, k))
        slots = sum(k for _, k in segs)
        print("人口 %d (base=%08X): 槽数 %d" % (dom, base, slots))
        print("   seg_b: " + ", ".join("%4du" % b for b, _ in segs))
        print("   seg_n: " + ", ".join("%4du" % k for _, k in segs))
        print("   末号: %d (上限 1023)" % (segs[-1][0] + segs[-1][1] * 4 + 3))


if __name__ == "__main__":
    main()
