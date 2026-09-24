import numpy as np
g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(int)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)

CELLS1 = [16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 136]
CELLS2 = [16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 136]

def dump(cells, y0, y1, label):
    print("="*110)
    print(label, "rows", y0, "..", y1-1)
    print("cell x: " + "  ".join("%-8d" % c for c in cells))
    for y in range(y0, y1):
        parts = []
        for c in cells:
            parts.append("".join("#" if ink[y, c+i] else "." for i in range(8)))
        print("y%3d  " % y + "  ".join(parts))
    print("ink:   " + "  ".join("%-8d" % ink[y0:y1, c:c+8].sum() for c in cells))

dump(CELLS1, 25, 38, "LINE1 (领航员第一行)")
dump(CELLS2, 41, 54, "LINE2 (领航员第二行)")
