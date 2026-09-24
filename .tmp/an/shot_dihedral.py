import numpy as np, os
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
raw=open(os.path.join(FD,"PokeRSFontChsMiddle(0xE0000).bin"),'rb').read()
def brick(b32):
    m=np.zeros((8,8),bool)
    for i in range(32):
        b=b32[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: m[r,cb]=True
        if b&0xF0: m[r,cb+1]=True
    return m
T=np.array([brick(raw[i*128+k*32:i*128+k*32+32]) for i in range(7168) for k in (0,1)])
TI=T.sum(axis=(2,1))

# 8 种二面体变换
variants={
    "原样":      lambda M: M,
    "水平镜像":  lambda M: M[:,:,::-1],
    "垂直镜像":  lambda M: M[:,::-1,:],
    "180°":      lambda M: M[:,::-1,::-1],
}
# 也试 ±1..3 像素平移
def shift(M,dy,dx):
    out=np.zeros_like(M)
    ys=slice(max(0,dy),8+min(0,dy)); yd=slice(max(0,-dy),8+min(0,-dy))
    xs=slice(max(0,dx),8+min(0,dx)); xd=slice(max(0,-dx),8+min(0,-dx))
    out[:,ys,xs]=M[:,yd,xd]
    return out

print("### 屏幕砖 vs 库砖（各种变换）最佳 d")
for (y0,lab) in ((24,"row1"),(40,"row2")):
    for x0 in (16,24,72,80,128,136):
        m=ink[y0:y0+16,x0:x0+8]
        if m.sum()<4: continue
        for tag,t in (("上",m[0:8,:]),("下",m[8:16,:])):
            if t.sum()<2: continue
            res=[]
            for vn,f in variants.items():
                V=f(T)
                d=(V!=t[None,:,:]).sum(axis=(2,1)); i=int(d.argmin())
                res.append((int(d[i]),vn,i))
            for dy in (-1,1):
                V=shift(T,dy,0)
                d=(V!=t[None,:,:]).sum(axis=(2,1)); i=int(d.argmin())
                res.append((int(d[i]),f"垂直移{dy}",i))
            for dx in (-1,1):
                V=shift(T,0,dx)
                d=(V!=t[None,:,:]).sum(axis=(2,1)); i=int(d.argmin())
                res.append((int(d[i]),f"水平移{dx}",i))
            res.sort()
            b=res[0]
            print(f"  {lab} x={x0:3d} {tag}: 最佳 d={b[0]:2d} [{b[1]}] 砖{b[2]//2}块{b[2]%2} 屏墨={int(t.sum())} 库墨={int(TI[b[2]])}")
