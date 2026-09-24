import os
from collections import Counter
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
for fn in ("PokeRSFontChsMiddle(0xE0000).bin","PokeRSFontChsMiddle_unshadow(0xE0000).bin",
           "PokeRSFontChsNormal(0xE0000).bin","PokeRSFontChsNormal_unshadow(0xE0000).bin"):
    p=os.path.join(FD,fn); raw=open(p,'rb').read()
    c=Counter()
    for b in raw[:128*64]:
        c[b&0xF]+=1; c[b>>4]+=1
    print(f"{fn}: nibble hist {sorted(c.items())}")
