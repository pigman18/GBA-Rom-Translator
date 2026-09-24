import numpy as np, re

def parse_bdf(path):
    out={}
    enc=None; bitmap=None; inb=False
    for line in open(path,'r',encoding='utf-8',errors='replace'):
        line=line.rstrip('\n')
        if line.startswith('ENCODING'):
            enc=int(line.split()[1])
        elif line.startswith('BITMAP'):
            bitmap=[]; inb=True
        elif line.startswith('ENDCHAR'):
            if enc is not None and bitmap is not None: out[enc]=bitmap
            bitmap=None; inb=False
        elif inb and line:
            bitmap.append(line.strip())
    return out

bdf = parse_bdf(r"C:/code/GBA-Rom-Translator/fonts/default/Middle.bdf")
print("BDF 字符数:", len(bdf))

# charmap
cmap_gid2uni={}
for line in open(r"C:/code/GBA-Rom-Translator/configs/POKEMON_RUBY_AXVJ00/charmap.txt",'r',encoding='utf-8',errors='replace'):
    line=line.strip()
    if not line or '=' not in line: continue
    k,v=line.split('=',1)
    if len(k)!=4: continue
    try: lead=int(k[:2],16); trail=int(k[2:],16)
    except: continue
    idx = lead
    if idx>=6:
        if idx>=0x1B: idx-=1
        idx-=1
    idx-=1
    gid=((idx<<8)|trail) & 0xFFFF
    cmap_gid2uni[gid]=v

raw=open(r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle(0xE0000).bin",'rb').read()
def show_ascii(rows):
    for r in rows: print("        "+r.replace('1','#').replace('0','.'))
def bdf16(bitmap):
    rows=[]
    for h in bitmap:
        v=int(h,16)
        rows.append("".join('1' if (v>>(15-c))&1 else '0' for c in range(16)))
    return rows
def bin16(gid):
    # 4 tiles: TL(0..31) TR(32..63) BL(64..95) BR(96..127)  -> 16x16
    b=raw[gid*128:(gid+1)*128]
    grid=[['0']*16 for _ in range(16)]
    for t in range(4):
        tr=t//2; tc=t%2
        for i in range(32):
            byte=b[t*32+i]; r=(tr*8)+i//4; c=(tc*8)+(i%4)*2
            if byte&0x0F: grid[r][c]='1'
            if byte&0xF0: grid[r][c+1]='1'
    return ["".join(x) for x in grid]

for ch in "宝可梦领航员":
    gids=[g for g,u in cmap_gid2uni.items() if u==ch]
    if not gids: print("no gid for", ch); continue
    gid=gids[0]
    uni=ord(ch)
    print(f"\n================= {ch}  gid={gid} (U+{uni:04X}) =================")
    print("  --- BDF (16x16) ---")
    if uni in bdf: show_ascii(bdf16(bdf[uni]))
    else: print("      (BDF 无此字符)")
    print(f"  --- .bin gid {gid} (16x16, 4 砖 TL/TR/BL/BR) ---")
    show_ascii(bin16(gid))
