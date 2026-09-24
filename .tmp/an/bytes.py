import numpy as np, hashlib
B=np.load('.tmp/zoom3/one_x.npy')
blk=(B[:,:,0]<40)&(B[:,:,1]<40)&(B[:,:,2]<40)
OBS=[('b1c0',8,16),('b1c1',8,24),('b1c2',8,32),('b1c3',8,40),
     ('b2c0',72,16),('b2c1',72,24),('b2c2',72,32),
     ('b3c0',104,16),('b3c1',104,24)]
seen={}
for name,y0,x0 in OBS:
    m=np.zeros((16,8),np.uint8)
    for r in range(16):
        for c in range(8):
            m[r,c]=1 if blk[y0+r,x0+c] else 0
    print(f"--- {name} y{y0} x{x0}")
    for r in range(16):
        # left=low nibble
        bs=[]
        for c in range(0,8,2):
            lo=0xF if m[r,c]   else 0
            hi=0xF if m[r,c+1] else 0
            bs.append((hi<<4)|lo)
        tag=""
        if bs[0]==bs[1] and bs[2]==bs[3]: tag=" [P,P,R,R]"
        print(f"   r{r:2d}  "+" ".join(f"{b:02X}" for b in bs)+tag)
    h=hashlib.md5(m.tobytes()).hexdigest()[:8]
    print(f"   md5={h}  墨={int(m.sum())}")
    seen.setdefault(h,[]).append(name)
print("\n相同内容分组:",{k:v for k,v in seen.items() if len(v)>1})
