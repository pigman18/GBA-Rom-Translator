import numpy as np
ROM=r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
d=open(ROM,'rb').read()
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)

# 屏幕 8x8 砖（行带 y0=24/40，x 全宽，按 8 对齐）
cells=[]
for y0 in (24,40):
    for x0 in range(16,232,8):
        m=ink[y0:y0+16,x0:x0+8]
        if m.sum()>=4:
            cells.append((y0,x0,m[0:8,:],m[8:16,:]))
print("屏幕 8x8 砖数:", len(cells)*2)

def mask8(seg,rev=False):
    m=np.zeros((8,8),bool)
    for r in range(8):
        b=seg[r]
        for c in range(8):
            bit = (b>>(7-c))&1 if not rev else (b>>c)&1
            m[r,c]=bool(bit)
    return m

def build(addr, stride, n, rev=False, plan='8x8'):
    off=addr-0x08000000
    out=[]
    for i in range(n):
        seg=d[off+i*stride: off+i*stride+(8 if plan=='8x8' else 16)]
        if plan=='8x8':
            out.append(mask8(seg,rev))
        else:
            # 16x16: 2 bytes/row
            m=np.zeros((16,16),bool)
            for r in range(16):
                w=(seg[2*r]<<8)|seg[2*r+1]
                for c in range(16):
                    m[r,c]=bool((w>>(15-c))&1) if not rev else bool((w>>c)&1)
            out.append(m)
    return np.array(out)

suite=[]
for addr,stride,n,lbl in ((0x081B49AC,8,600,"font1/4@081B49AC 8B/字"),
                          (0x081B51AC,32,600,"font2/5@081B51AC 32B/字")):
    for rev in (False,True):
        A=build(addr,stride,n,rev,'8x8')
        suite.append((f"{lbl} rev={rev} 8x8", A))

best=[]
for lbl,A in suite:
    tot=0; nz=0; perfect=0; mind=999; cnt=0
    for (y0,x0,T,B) in cells:
        for t in (T,B):
            if t.sum()<3: continue
            dd=(A!=t[None,:,:]).sum(axis=(2,1)); i=int(dd.argmin())
            cnt+=1; tot+=int(dd[i])
            if dd[i]==0: perfect+=1
            mind=min(mind,int(dd[i]))
    print(f"  {lbl:34s} 比对 {cnt} 砖, 完美匹配 {perfect}, 平均 d={tot/max(cnt,1):.1f}, 最小 d={mind}")
