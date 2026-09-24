import numpy as np
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)

def dump(x0,x1,y0,y1,lbl):
    print(f"### {lbl}  x{x0}..{x1-1} y{y0}..{y1-1}")
    print("      " + "".join(str(x//10%10) for x in range(x0,x1)))
    print("      " + "".join(str(x%10) for x in range(x0,x1)))
    for y in range(y0,y1):
        print(f"{y:4d}  " + "".join('#' if ink[y,x] else '.' for x in range(x0,x1)))
    print()

dump(14,36,24,40,"row1 第1-2格")
dump(40,56,24,40,"row1 第3-4格")
dump(70,92,24,40,"row1 第7-8格")
dump(126,148,24,40,"row1 第14-15格")
dump(184,224,24,40,"row1 右端")
dump(14,36,40,56,"row2 第1-2格")
