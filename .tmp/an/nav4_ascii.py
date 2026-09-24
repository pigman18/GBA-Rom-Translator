# -*- coding: utf-8 -*-
"""精确 ASCII dump：每个像素一个字符，看清畸变结构。"""
import numpy as np
a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)

PAL = {(255,255,255): '.', (33,132,255): '#'}
def ch(p):
    t = tuple(int(v) for v in p)
    if t in PAL: return PAL[t]
    # 近似归类
    d_ink = abs(t[0]-33)+abs(t[1]-132)+abs(t[2]-255)
    d_wht = abs(t[0]-255)+abs(t[1]-255)+abs(t[2]-255)
    if d_ink < d_wht: return '#'
    return '.'

def dump(x0, x1, y0, y1, title):
    print("\n" + "="*100)
    print(title)
    print("     " + "".join(str((x//10)%10) if x%10==0 else " " for x in range(x0,x1)))
    print("     " + "".join(str(x%10) for x in range(x0,x1)))
    for y in range(y0, y1):
        print("%4d " % y + "".join(ch(a[y,x]) for x in range(x0,x1)))

dump(8, 48, 22, 40, "区域1: x=8..47, y=22..39  (第一行文字)")
dump(8, 48, 40, 56, "区域2: x=8..47, y=40..55  (第二行文字)")
dump(64, 104, 22, 40, "区域3: x=64..103, y=22..39")
dump(120, 152, 22, 40, "区域4: x=120..151, y=22..39")
