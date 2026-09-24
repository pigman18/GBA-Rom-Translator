import numpy as np, hashlib, os
ROM=r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
rom=open(ROM,'rb').read()
WORK=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
import glob
for name in sorted(os.listdir(WORK)):
    if not name.endswith(".bin"): continue
    size=os.path.getsize(os.path.join(WORK,name))
    # 找 vaddr：全部试 0x08000000 起
    print(f"{name:48s} size={size}")
print()
ADDR=0x09400000
off=ADDR-0x08000000
for name in ("PokeRSFontChsMiddle(0xE0000).bin","PokeRSFontChsMiddle_unshadow(0xE0000).bin"):
    w=open(os.path.join(WORK,name),'rb').read()
    seg=rom[off:off+len(w)]
    print(f"{name}: rom==work? {seg==w}  rom sha1 {hashlib.sha1(seg).hexdigest()[:12]}  work sha1 {hashlib.sha1(w).hexdigest()[:12]}")
    if seg!=w:
        diff=[i for i in range(len(w)) if seg[i]!=w[i]]
        print(f"   差异字节数 {len(diff)}  首 10: {diff[:10]}")
