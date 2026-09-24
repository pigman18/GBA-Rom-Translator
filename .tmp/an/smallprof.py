import numpy as np
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
NG=7168; SZ=128
def prof(name,a):
    base=a-0x08000000
    L=np.frombuffer(ROM,np.uint8,count=NG*SZ,offset=base).reshape(NG,SZ)
    ink=(L>0)
    rows=np.zeros(16,int)
    cols=np.zeros(16,int)
    for g in range(0,NG,11):
        blk=L[g]
        for half,tb in ((0,0),(1,32)):
            for r in range(8):
                row=blk[tb+r*4:tb+r*4+4]
                for c in range(4):
                    b=row[c]
                    hi=(b>>4)!=0; lo=(b&0xF)!=0
                    rows[half*8+r]+= hi+lo
                    cols[c*2]+=hi      # hi = 右 or 左?
                    cols[c*2+1]+=lo
    n=len(range(0,NG,11))
    print(f"[{name}] 每格平均: 行 "+" ".join(str(v//n) for v in rows))
    print(f"[{name}]           列 "+" ".join(str(v//n) for v in cols))
prof("SMALL@0x09100000",0x09100000)
prof("NORMAL@0x09000000",0x09000000)
prof("MIDDLE@0x09400000",0x09400000)
