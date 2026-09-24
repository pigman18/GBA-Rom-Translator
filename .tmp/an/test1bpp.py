import numpy as np
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
NG=7168
B=np.load('.tmp/zoom3/one_x.npy')
blk=(B[:,:,0]<40)&(B[:,:,1]<40)&(B[:,:,2]<40)
# 观测格（格顶 y，左 x）
OBS={'b1c0':(8,16),'b1c1':(8,24),'b1c2':(8,32),'b1c3':(8,40),
     'b2c0':(72,16),'b2c1':(72,24),'b2c2':(72,32),
     'b3c0':(104,16),'b3c1':(104,24)}
def obs_mask(y0,x0):
    m=np.zeros((16,8),bool)
    for r in range(16):
        for c in range(8):
            m[r,c]=blk[y0+r,x0+c]
    return m

def cell_from_1bpp(bits,width,rows,line_off):
    cell=np.zeros(128,np.uint8)
    bit=0
    for y in range(rows):
        r=y+line_off
        if r>=16: break
        base = (0 if r<8 else 32) + (r&7)*4
        for x in range(width):
            b=bits[bit>>3]; on=(b>>(7-(bit&7)))&1
            bit+=1
            if not on: continue
            if x<8:
                cell[base+(x>>1)] |= (0xF0 if (x&1) else 0x0F)
    return cell
def mask_from_cell(cell):
    m=np.zeros((16,8),bool)
    for half,tb in ((0,0),(1,32)):
        for r in range(8):
            row=cell[tb+r*4:tb+r*4+4]
            for c in range(4):
                b=row[c]
                m[half*8+r, 2*c]   = (b&0xF)!=0
                m[half*8+r, 2*c+1] = (b>>4)!=0
    return m

LIBS=[('BIG',0x09500000,16,11,11,2),('MIDSMALL',0x09600000,11,9,9,5),('MIDDLE1B',0x09700000,13,9,11,2)]
for name,a,stride,w,h,ro in LIBS:
    base=a-0x08000000
    allm=np.array([mask_from_cell(cell_from_1bpp(ROM[base+g*stride:base+g*stride+stride],w,h,ro)) for g in range(NG)])
    print(f"\n##### {name} stride={stride} {w}x{h} rowoff={ro}")
    for cn,(y0,x0) in OBS.items():
        T=obs_mask(y0,x0)
        d=(allm!=T).sum(axis=(1,2))
        o=np.argsort(d)[:3]
        print(f"  {cn} 墨{T.sum():3d}: 最佳 gid={o.tolist()} d={d[o].tolist()}")
