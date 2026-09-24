import numpy as np
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
NG=7168; SZ=128
for name,a in [('MIDDLE',0x09400000),('SMALL',0x09100000)]:
    base=a-0x08000000
    L=np.frombuffer(ROM,np.uint8,count=NG*SZ,offset=base).reshape(NG,SZ)
    S=np.concatenate([L[:,0:32].reshape(NG,8,4), L[:,32:64].reshape(NG,8,4)],axis=1)
    eq = (S[:,:,0]==S[:,:,1]) & (S[:,:,2]==S[:,:,3])
    print(f"[{name}] 全库 16 行中满足 b0==b1&&b2==b3 的**行**数: {eq.sum()} / {NG*16}  = {eq.mean()*100:.2f}%")
    eq2 = (S[:,:,0]==S[:,:,1])
    print(f"[{name}]   b0==b1 比例 {eq2.mean()*100:.1f}%   (b2==b3) {((S[:,:,2]==S[:,:,3]).mean()*100):.1f}%")
    # 每字是否全部 16 行都成对
    print(f"[{name}]   整字 16 行全成对: {eq.all(1).sum()} / {NG}")
    if name=='MIDDLE':
        for g in (1207,3203,3732):
            print(f"\n--- MIDDLE gid={g} 的 16 行 (行=r0..r15)")
            for r in range(16):
                print(f"   r{r:2d}  {' '.join(f'{b:02X}' for b in S[g,r])}")
            print("   该字 16 行全成对?", bool(eq[g].all()))
