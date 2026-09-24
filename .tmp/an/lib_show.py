import numpy as np, sys
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
def l4(b64):
    out=np.zeros((16,8),bool)
    for i in range(64):
        b=b64[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: out[r,cb]=True
        if b&0xF0: out[r,cb+1]=True
    return out
raw=open(FD+r"\PokeRSFontChsMiddle(0xE0000).bin",'rb').read()
def show(gid):
    m=l4(raw[gid*128:gid*128+64])
    print(f"--- Middle gid {gid} (墨 {int(m.sum())})")
    for r in range(16):
        print("      "+"".join('#' if m[r,c] else '.' for c in range(8)))
for g in [int(x) for x in sys.argv[1:]]:
    show(g)
