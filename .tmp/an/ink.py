import numpy as np
B=np.load('.tmp/zoom3/one_x.npy')   # 160x240x3
def isblack(p): return p[0]<40 and p[1]<40 and p[2]<40
def isblue(p):  return p[2]>150 and p[0]<120 and p[1]>90
blk=np.zeros((160,240),bool); blu=np.zeros((160,240),bool)
for y in range(160):
    for x in range(240):
        p=B[y,x]
        if isblack(p): blk[y,x]=True
        elif isblue(p): blu[y,x]=True
print("黑",blk.sum(),"蓝",blu.sum())
def bands(m):
    r=m.sum(1); out=[];s=None
    for i,v in enumerate(r>0):
        if v and s is None: s=i
        elif not v and s is not None: out.append((s,i-1,int(r[s:i].max()))); s=None
    if s is not None: out.append((s,159,int(r[s:].max())))
    return out
print("黑行带:")
for a,b,mx in bands(blk):
    xs=np.where(blk[a:b+1].any(0))[0]
    print(f"  y{a}..{b} (h={b-a+1})  x{xs.min()}..{xs.max()} n={blk[a:b+1].sum()}")
print("蓝行带:")
for a,b,mx in bands(blu):
    xs=np.where(blu[a:b+1].any(0))[0]
    print(f"  y{a}..{b} (h={b-a+1})  x{xs.min()}..{xs.max()} n={blu[a:b+1].sum()}")
