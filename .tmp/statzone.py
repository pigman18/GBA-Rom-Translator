# -*- coding: utf-8 -*-
"""检查 EWRAM 顶部 0x3FF00..0x40000 是否是游戏自己的数据区。
对比多个 dump（不同场景）该区是否变化 => 游戏是否在写。
"""
import sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tags = ["orgparty","org2","orgObs","v_opt","v_party","o_menu","t_info","x_sum2"]
data = {}
for t in tags:
    p = T / f"drive_{t}_ewram.bin"
    if p.exists():
        data[t] = p.read_bytes()
for t, b in data.items():
    seg = b[0x3FF00:0x40000]
    nz = sum(1 for x in seg if x)
    # 找非零区间
    runs = []
    i = 0
    while i < len(seg):
        if seg[i]:
            j = i
            while j < len(seg) and (seg[j] or (j+1 < len(seg) and seg[j+1])):
                j += 1
            runs.append((0x3FF00+i, 0x3FF00+j))
            i = j
        i += 1
    print("%-10s 非零=%3d  非零区段=%s" % (t, nz, runs[:8]))
print()
# 两两比较
ks = list(data)
for i in range(len(ks)):
    for j in range(i+1, len(ks)):
        a, b = data[ks[i]], data[ks[j]]
        seg_a, seg_b = a[0x3FF00:0x40000], b[0x3FF00:0x40000]
        d = [k for k in range(len(seg_a)) if seg_a[k] != seg_b[k]]
        # 压缩连续
        sets = []
        for k in d:
            if sets and k == sets[-1][1]:
                sets[-1][1] = k+1
            else:
                sets.append([k, k+1])
        print("%-10s vs %-10s 差异 %3d 字节  %s" % (ks[i], ks[j], len(d),
              [("0x%05X-0x%05X" % (0x3FF00+s, 0x3FF00+e)) for s, e in sets[:6]]))
