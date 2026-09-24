import numpy as np, os
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
def l4(b64):
    out=np.zeros((16,8),bool)
    for i in range(64):
        b=b64[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: out[r,cb]=True
        if b&0xF0: out[r,cb+1]=True
    return out
raw=open(os.path.join(FD,"PokeRSFontChsMiddle(0xE0000).bin"),'rb').read()
L=np.array([l4(raw[i*128:i*128+64]) for i in range(7168)])

def shx(M,dx):
    out=np.zeros_like(M)
    if dx>0: out[:,:,dx:]=M[:,:,:-dx]
    elif dx<0: out[:,:,:dx]=M[:,:,-dx:]
    else: out=M
    return out
def shy(M,dy):
    out=np.zeros_like(M)
    if dy>0: out[:,dy:,:]=M[:,:-dy,:]
    elif dy<0: out[:,:dy,:]=M[:,-dy:,:]
    else: out=M
    return out

tests=[]
for dx in (1,2,3):
    tests.append((f"|x+{dx}", lambda M,dx=dx: M|shx(M,dx)))
    tests.append((f"|x-{dx}", lambda M,dx=dx: M|shx(M,-dx)))
for dy in (1,2):
    tests.append((f"|y+{dy}", lambda M,dy=dy: M|shy(M,dy)))
for dx in (1,2):
    tests.append((f"^x+{dx}", lambda M,dx=dx: M^shx(M,dx)))

for (y0,lab) in ((24,"row1"),(40,"row2")):
    for x0 in (16,24,72,80,128,136):
        M=ink[y0:y0+16,x0:x0+8]
        if M.sum()<8: continue
        best=[]
        for tn,f in tests:
            V=f(L)
            d=(V!=M[None,:,:]).sum(axis=(2,1)); i=int(d.argmin())
            best.append((int(d[i]),tn,i))
        best.sort()
        print(f"  {lab} x={x0:3d} 屏墨={int(M.sum()):3d}  ->  " + "  ".join(f"d={b[0]} [{b[1]}] gid={b[2]}" for b in best[:3]))
