# -*- coding: utf-8 -*-
"""slabdemand.py — 逐页量各「人口」（窗口 tileData）的槽需求峰值。

用法: python .tmp/slabdemand.py [tag ...]
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
TR = 0x3C000
POOLS = {0: 0x06004000, 1: 0x06008000, 2: 0x06000000}


def main(tags):
    for tag in tags:
        p = T / ("drive_%s_ewram.bin" % tag)
        if not p.exists():
            print("== %-9s (无 dump)" % tag)
            continue
        ew = p.read_bytes()
        g = lambda o: struct.unpack_from("<I", ew, TR + o)[0]
        # 窗口表：win → (tpl, tileData)
        wtd = {}
        for i in range(24):
            o = 0x20 + i * 32
            win, tpl, td = g(o), g(o + 4), g(o + 8)
            if win:
                wtd[win] = td
        per = {}
        for i in range(369):
            o = 0x320 + i * 20
            w = [g(o + j * 4) for j in range(5)]
            if not any(w):
                continue
            win = w[0]
            td = wtd.get(win, 0)
            dom = {v: k for k, v in POOLS.items()}.get(td, 1)
            t0, t1 = w[3] & 0xFFFF, (w[3] >> 16) & 0xFFFF
            s = per.setdefault(dom, {"slots": set(), "rec": 0, "win": set()})
            s["rec"] += 1
            s["win"].add(win)
            if t0:
                s["slots"].add(t0)
            if t1:
                s["slots"].add(t1)
        print("== %-9s 窗口 %d 条" % (tag, sum(s["rec"] for s in per.values())))
        for dom in sorted(per):
            s = per[dom]
            print("     人口 %d  记录 %-4d  独立砖 %-4d (≈%d 槽)  win=%s"
                  % (dom, s["rec"], len(s["slots"]), len(s["slots"]) / 2,
                     ",".join("%08X" % w for w in sorted(s["win"]))))


if __name__ == "__main__":
    main(sys.argv[1:] or ["t_title", "t_menu", "t_bag", "t_bag2", "t_party",
                          "t_sum", "t_sum2", "t_info", "t_moves"])
