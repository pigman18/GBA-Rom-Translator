import numpy as np
g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(int)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)

# 列墨量分布（哪些列有墨）
colsum = ink.sum(axis=0)
print("--- 有墨的列区间 ---")
runs = []
inrun = False
for x in range(240):
    if colsum[x] > 0 and not inrun:
        s = x; inrun = True
    elif colsum[x] == 0 and inrun:
        runs.append((s, x-1)); inrun = False
if inrun: runs.append((s, 239))
print(runs)

print()
for band, (y0, y1) in [("LINE1", (24, 38)), ("LINE2", (40, 54))]:
    print("="*100)
    print(band, "rows", y0, y1)
    for x0 in (8, 88, 168):
        print("--- x %d..%d ---" % (x0, x0+79))
        hdr = "    " + "".join(str((x0+i)//10 % 10) for i in range(80))
        print(hdr)
        hdr2 = "    " + "".join(str((x0+i) % 10) for i in range(80))
        print(hdr2)
        for y in range(y0, y1):
            line = "".join("#" if ink[y, x0+i] else "." for i in range(80))
            print("y%3d %s" % (y, line))
        print()
