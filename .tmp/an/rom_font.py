import numpy as np, hashlib, os
ROM=r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
rom=open(ROM,'rb').read()
print("ROM size", len(rom))
WORK=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
for name,addr,size in (
    ("PokeRSFontChsMiddle(0xE0000).bin",            0x09400000, 917504),
    ("PokeRSFontChsMiddle_unshadow(0xE0000).bin",   0x09400000, 917504),
):
    w=open(os.path.join(WORK,name),'rb').read()
    seg=rom[addr:addr+size]
    same = (seg==w)
    print(f"{name}: rom==work? {same}   rom sha1 {hashlib.sha1(seg).hexdigest()[:12]}  work sha1 {hashlib.sha1(w).hexdigest()[:12]}")

# 分别试两个版本，看哪个能匹配屏上砖
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)
def bricks(raw):
    out=[]
    for gid in range(len(raw)//128):
        for k in (0,1):
            b=raw[gid*128+k*32:gid*128+k*32+32]
            m=np.zeros((8,8),bool)
            for i in range(32):
                bb=b[i]; r=i//4; cb=(i%4)*2
                if bb&0x0F: m[r,cb]=True
                if bb&0xF0: m[r,cb+1]=True
            out.append(m)
    return np.array(out)

for name in ("PokeRSFontChsMiddle(0xE0000).bin","PokeRSFontChsMiddle_unshadow(0xE0000).bin"):
    raw=open(os.path.join(WORK,name),'rb').read()
    T=bricks(raw); TI=T.sum(axis=(2,1))
    print(f"\n### {name}: {len(T)} 砖, 有墨 {int((TI>0).sum())}")
    for (y0,lab) in ((24,"row1"),(40,"row2")):
        for x0 in (16,24,72,80,128,136):
            m=ink[y0:y0+16,x0:x0+8]
            if m.sum()<4: continue
            out=[]
            for tag,t in (("上",m[0:8,:]),("下",m[8:16,:])):
                if t.sum()<2: out.append(f"{tag}:空"); continue
                d=(T!=t[None,:,:]).sum(axis=(1,2))
                i=int(d.argmin())
                out.append(f"{tag}: d={int(d[i])} @砖{i//2}块{i%2} 库墨={int(TI[i])} 屏墨={int(t.sum())}")
            print(f"  {lab} x={x0:3d}  "+"   ".join(out))
